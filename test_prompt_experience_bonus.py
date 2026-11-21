"""Regression coverage for a format-dependent experience adjustment."""
import unittest
import leveling
import prompt
from models import Player


class PromptExperienceTests(unittest.TestCase):
    @staticmethod
    def ninja(fmt=None):
        return Player("PromptRewardTester", "PromptRewardTester",
                      village_rank="genin",
                      prompt_string=prompt.PRESETS["biran"] if fmt is None else fmt)

    def test_exact_preset_gets_extra_xp(self):
        p = self.ninja()
        leveling.grant_experience(p, 100)
        self.assertEqual((p.experience, p.xp_bonus_remainder), (105, 0))

    def test_remainder_kept_across_save_reload(self):
        p = self.ninja()
        for _ in range(19):
            leveling.grant_experience(p, 1)
        self.assertEqual((p.experience, p.xp_bonus_remainder), (19, 19))
        p = Player.from_dict(p.to_dict())
        leveling.grant_experience(p, 1)
        self.assertEqual((p.experience, p.xp_bonus_remainder), (21, 0))

    def test_other_formats_have_normal_xp(self):
        p = self.ninja(prompt.PRESETS["default"])
        leveling.grant_experience(p, 100)
        p.prompt_string = "off"
        leveling.grant_experience(p, 100)
        p.prompt_string = "&RHP:%h/%H&x"
        leveling.grant_experience(p, 100)
        self.assertEqual(p.experience, 300)
        p.prompt_string = prompt.PRESETS["biran"]
        leveling.grant_experience(p, 100)
        self.assertEqual(p.experience, 405)

    def test_remainder_pauses_outside_biran(self):
        p = self.ninja()
        leveling.grant_experience(p, 1)
        p.prompt_string = prompt.PRESETS["default"]
        leveling.grant_experience(p, 100)
        self.assertEqual((p.experience, p.xp_bonus_remainder), (101, 1))
        p.prompt_string = prompt.PRESETS["biran"]
        for _ in range(19):
            leveling.grant_experience(p, 1)
        self.assertEqual((p.experience, p.xp_bonus_remainder), (121, 0))

    def test_rank_cap_still_applies(self):
        p = self.ninja()
        p.level = 35
        p.experience = leveling.cumulative_xp_for_level(35)
        leveling.grant_experience(p, 100)
        self.assertEqual(p.experience, leveling.cumulative_xp_for_level(35))
        self.assertEqual(p.xp_bonus_remainder, 0)


if __name__ == "__main__":
    unittest.main()
