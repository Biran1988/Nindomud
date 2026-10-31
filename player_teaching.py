"""Player-to-player shinobi teaching (same-class mastery transfer).

A mastered (100%+) same-class player may teach a skill that the other
player has already unlocked but only knows at 0-5%. The lesson starts the
student at 45%, costs no practice points and satisfies the first-lesson
gate. It does not teach locked, unknown, or other-class techniques.
"""

import data_jutsu
import skill_training
import storage


def command(session, args):
    if len(args) < 2:
        session.send("Usage: teach <player> <unlocked skill or jutsu>")
        return
    teacher = session.player
    if session.combat_target or session.pvp_target:
        session.send("Finish fighting before teaching another ninja.")
        return
    name = args[0].casefold()
    recipients = [s for s in session.active_sessions()
                  if s is not session and getattr(s, "player", None)
                  and s.player.room_vnum == teacher.room_vnum
                  and s.player.name.casefold() == name]
    if len(recipients) != 1:
        session.send("That player must be present in your room. Use their full name.")
        return
    recipient = recipients[0]
    student = recipient.player
    if recipient.combat_target or recipient.pvp_target:
        session.send("The student must finish fighting before a lesson.")
        return
    if teacher.primary_class != student.primary_class:
        session.send("Only ninja of the same primary class can teach one another.")
        return
    query = " ".join(args[1:]).strip().casefold()
    matches = [skill for skill in student.learned_skills if
               skill.casefold() == query or query in skill.casefold()]
    exact = [skill for skill in matches if skill.casefold() == query]
    if exact:
        matches = exact
    if len(matches) != 1:
        session.send("Choose one skill the student has already unlocked by its full name."
                     + (" Matches: " + ", ".join(matches) if matches else ""))
        return
    skill = matches[0]
    if skill not in teacher.learned_skills:
        session.send("You can only teach a skill that you have personally learned.")
        return
    if teacher.skill_proficiencies.get(skill, 0) < 100:
        session.send(f"You must reach 100% mastery of {skill} to teach it.")
        return
    # Category restriction applies to jutsu, not shared general skills.
    technique = next((j for j in data_jutsu.JUTSU.values()
                      if j["display_name"].casefold() == skill.casefold()), None)
    if technique:
        required_class = technique.get("class_requirement", "")
        if required_class not in ("", "all", "general", teacher.primary_class):
            session.send("That technique belongs to a different ninja class.")
            return
        if student.level < technique.get("level_requirement", 1):
            session.send("The student has not reached the required level for this technique.")
            return
    current = student.skill_proficiencies.get(skill, 0)
    if current > 5:
        session.send(f"{student.name} already knows {skill} at {current}%. Teaching is only for students at 5% or less.")
        return
    student.skill_proficiencies[skill] = 45
    # A real player-teaching lesson substitutes for the NPC teacher's
    # first practice, without consuming any practice point or session.
    skill_training.mark_practiced(student, skill)
    storage.save_player(student)
    session.send(f"You teach {student.name} {skill}, raising their proficiency from {current}% to 45%.")
    recipient.send(f"{teacher.name} teaches you {skill}. Your proficiency rises to 45% without using a practice point.")
    import room_actions
    room_actions.emit(session, f"{teacher.name} teaches {student.name} a shinobi technique.")
