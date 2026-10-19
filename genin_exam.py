"""Hardcoded Genin Academy written exam administered only by Iruka, mob VNUM 11.

At level 10, an Academy Student needs all five starting martial/ninja
techniques mastered at 100% to begin. Ten different Naruto-anime questions
are selected from a twenty-question pool and each question's four answer
positions are independently shuffled. Ten correct answers graduate the
student; a single wrong answer ends that attempt.
"""
import random

IRUKA_VNUM = 11
MIN_LEVEL = 10
MASTERED_PERCENT = 100
STARTER_SKILLS = (
    "Shadow Shuriken Technique",
    "Dynamic Entry",
    "Demonic Illusion: Hell Viewing Technique",
    "Throw Shuriken",
    "Strong Fist Style",
)
QUESTIONS_PER_EXAM = 10

# question, correct option, and three plausible wrong options.
# Facts from the original Naruto anime and Naruto Shippuden.
START_PHRASE = "start genin exam"

QUESTION_BANK = (
    ("Who is the jonin leader of Naruto, Sasuke, and Sakura's original Team 7?",
     "Kakashi Hatake", "Might Guy", "Asuma Sarutobi", "Kurenai Yuhi"),
    ("What is the name of the Nine-Tailed Fox sealed inside Naruto?",
     "Kurama", "Shukaku", "Gyuki", "Matatabi"),
    ("Who serves as the Third Hokage?",
     "Hiruzen Sarutobi", "Minato Namikaze", "Tobirama Senju", "Tsunade"),
    ("Who teaches Naruto the Rasengan?",
     "Jiraiya", "Iruka Umino", "Orochimaru", "Yamato"),
    ("Who is the medical ninjutsu mentor who trains Sakura?",
     "Tsunade", "Shizune", "Kurenai Yuhi", "Anko Mitarashi"),
    ("Which member of Team 7 leaves Konoha to train under Orochimaru?",
     "Sasuke Uchiha", "Sakura Haruno", "Naruto Uzumaki", "Sai"),
    ("Which organization wears black cloaks patterned with red clouds?",
     "Akatsuki", "ANBU", "Root", "Sound Four"),
    ("Which tailed beast is sealed inside Gaara at the start of Naruto?",
     "Shukaku", "Kurama", "Isobu", "Chomei"),
    ("Who attacks the Third Hokage during the Konoha Crush, leading to his death?",
     "Orochimaru", "Itachi Uchiha", "Kabuto Yakushi", "Pain"),
    ("Which forbidden technique does Naruto learn from the Scroll of Seals?",
     "Multiple Shadow Clone Technique", "Chidori", "Rasengan", "Flying Thunder God"),
    ("Who is known as the Copy Ninja?",
     "Kakashi Hatake", "Might Guy", "Asuma Sarutobi", "Killer B"),
    ("Which dojutsu is famously associated with the Uchiha clan?",
     "Sharingan", "Byakugan", "Rinnegan", "Ketsuryugan"),
    ("Which hidden village does Gaara represent?",
     "Hidden Sand Village", "Hidden Mist Village", "Hidden Stone Village", "Hidden Rain Village"),
    ("Where does Naruto train in the ways of Toad Sage Mode?",
     "Mount Myoboku", "Ryuchi Cave", "Shikkotsu Forest", "Valley of the End"),
    ("What ninja discipline does Rock Lee specialize in?",
     "Taijutsu", "Medical ninjutsu", "Sealing techniques", "Puppetry"),
    ("Who is Team 10's original jonin instructor?",
     "Asuma Sarutobi", "Kakashi Hatake", "Might Guy", "Ebisu"),
    ("Which Akatsuki member is paired with Kisame?",
     "Itachi Uchiha", "Deidara", "Hidan", "Sasori"),
    ("Who is Naruto Uzumaki's father?",
     "Minato Namikaze", "Hashirama Senju", "Hiruzen Sarutobi", "Jiraiya"),
    ("Who is Naruto Uzumaki's mother?",
     "Kushina Uzumaki", "Mikoto Uchiha", "Tsunade", "Konan"),
    ("Who among Team Guy possesses the Byakugan?",
     "Neji Hyuga", "Rock Lee", "Tenten", "Might Guy"),
)


def iruka_here(session):
    """An alive, spawned Iruka with the exact template VNUM must be present."""
    import combat
    player = getattr(session, "player", None)
    if player is None:
        return None
    return next(
        (mob for mob in combat.mobs_in_room(player.room_vnum)
         if mob.template_vnum == IRUKA_VNUM and mob.health > 0),
        None,
    )


def missing_masteries(player):
    known = getattr(player, "learned_skills", ())
    proficiencies = getattr(player, "skill_proficiencies", {})
    return [
        (skill, proficiencies.get(skill, 0))
        for skill in STARTER_SKILLS
        if skill not in known or proficiencies.get(skill, 0) < MASTERED_PERCENT
    ]


def start_exam(session):
    """Begin only when the player speaks 'say Start Genin exam' near Iruka."""
    player = getattr(session, "player", None)
    if player is None or iruka_here(session) is None:
        session.send("Iruka (mob VNUM 11) must be here to conduct the Genin Exam.")
        return False
    if getattr(session, "iruka_exam", None) is not None:
        session.send('Iruka says, "Finish the exam in progress, or type cancel."')
        return False
    if player.village_rank != "academy student":
        session.send('Iruka says, "You have already left the Academy Student rank."')
        return False
    if player.level < MIN_LEVEL:
        session.send(f'Iruka says, "Reach level {MIN_LEVEL} before taking my Genin Exam."')
        return False
    missing = missing_masteries(player)
    if missing:
        session.send('Iruka says, "Master all five fundamentals before attempting my exam."')
        for skill, percent in missing:
            session.send(f"  {skill}: {percent}/{MASTERED_PERCENT}%")
        return False
    if (getattr(session, "combat_target", None) is not None
            or getattr(session, "pvp_target", None) is not None
            or getattr(session, "pending_cast", None) is not None
            or getattr(session, "controlled_clone", None) is not None):
        session.send('Iruka says, "Finish your current fight or technique first."')
        return False

    question_ids = random.sample(range(len(QUESTION_BANK)), QUESTIONS_PER_EXAM)
    previous = getattr(session, "_iruka_previous_questions", ())
    if set(question_ids) == set(previous):
        # Ensure two consecutive attempts never present the exact same set.
        replacement = next(i for i in range(len(QUESTION_BANK)) if i not in question_ids)
        question_ids[-1] = replacement
    session._iruka_previous_questions = tuple(question_ids)
    paper = []
    for qid in question_ids:
        question, correct, *incorrect = QUESTION_BANK[qid]
        choices = [correct, *incorrect]
        random.shuffle(choices)
        paper.append((question, choices, choices.index(correct)))
    session.iruka_exam = {"room_vnum": player.room_vnum, "paper": paper, "index": 0}
    session.send("&YIruka: Ten Naruto questions. You need TEN correct answers "
                 "to earn your Genin headband. One wrong answer fails this attempt.&x")
    session.send("Answer with A, B, C, or D (or 1-4). Type cancel to abandon the exam.")
    _show_question(session)
    return True


def _show_question(session):
    state = session.iruka_exam
    question, choices, _correct_index = state["paper"][state["index"]]
    session.send(f"&CGenin Written Exam: Question {state['index'] + 1}/{QUESTIONS_PER_EXAM}&x")
    session.send(f'Iruka asks, "{question}"')
    for letter, answer in zip("ABCD", choices):
        session.send(f"  {letter}) {answer}")


def handle_answer(session, line):
    """Consume commands while writing an exam; false when no exam exists."""
    state = getattr(session, "iruka_exam", None)
    if state is None:
        return False
    if session.player.room_vnum != state["room_vnum"] or iruka_here(session) is None:
        session.iruka_exam = None
        session.send("Iruka is no longer here. The unfinished exam has been cancelled.")
        return True

    response = line.strip().lower()
    if response in ("cancel", "forfeit", "stop"):
        session.iruka_exam = None
        session.send('Iruka says, "You may return when you are ready."')
        return True
    if response.startswith("answer "):
        response = response[7:].strip()
    answer_map = {"a": 0, "b": 1, "c": 2, "d": 3,
                  "1": 0, "2": 1, "3": 2, "4": 3}
    if response not in answer_map:
        session.send("Answer A, B, C, or D (or 1-4); type cancel to stop.")
        return True

    # Another guard against mutable ranks/mastery mid-exam via staff actions.
    if session.player.village_rank != "academy student" or missing_masteries(session.player):
        session.iruka_exam = None
        session.send('Iruka says, "Your eligibility changed. The exam is cancelled."')
        return True

    question, options, correct = state["paper"][state["index"]]
    if answer_map[response] != correct:
        session.iruka_exam = None
        session.send('&RIncorrect. Iruka ends your exam. You must try again from the beginning.&x')
        return True

    state["index"] += 1
    if state["index"] < QUESTIONS_PER_EXAM:
        session.send("&GCorrect!&x")
        _show_question(session)
        return True

    # Only this one place can issue the Genin reward upon passing.
    session.iruka_exam = None
    import kage
    import data_headbands
    import storage
    player = session.player
    player.village_rank = "genin"
    data_headbands.apply_rank_headband(player, "genin")
    kage.award_genin_mission_points_if_applicable(session, player, "genin")
    storage.save_player(player)
    session.send('&GIruka says, "Perfect score! Congratulations, you are now a Genin!"&x')
    kage.announce_rank_up(player.name, "genin")
    return True
