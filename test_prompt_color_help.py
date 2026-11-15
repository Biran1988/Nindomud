"""Live-colored sample help and accurate prompt customization reference."""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import colors
import commands
import help_system
import prompt
from models import Player


class PromptAndColorHelpTests(unittest.TestCase):
    @staticmethod
    def page(keyword):
        matches = [e for e in help_system.DEFAULT_HELP_ENTRIES
                   if e['primary_keyword'] == keyword]
        assert len(matches) == 1, keyword
        return matches[0]

    def test_packaged_help_pages_match_system_defaults(self):
        for keyword in ('prompt', 'colors'):
            entry = json.loads((Path(__file__).parent / 'helpfiles' /
                                f'{keyword}.json').read_text(encoding='utf-8'))
            page = self.page(keyword)
            for key in ('title','keywords','body'):
                self.assertEqual(entry[key],page[key])

    def test_all_prompt_tokens_documented_and_presets_listed(self):
        body = self.page('prompt')['body']
        for token in ('%h','%H','%c','%C','%s','%S','%x','%X','%q',
                      '%r','%m','%l','%v','%k','%p','%e','%n','%V',
                      '%t','%a','%d','%E','%%'):
            with self.subTest(token=token):
                self.assertIn(token,body)
        for name in prompt.PRESETS:
            self.assertIn('prompt '+name,body)
        self.assertIn('staff',body.lower())
        self.assertIn('blank',body.lower())
        self.assertIn('PROMPT OFF',body.upper())
        self.assertIn('PROMPT DEFAULT',body.upper())

    def test_prompt_help_opens_full_help_without_modifying_format(self):
        player=Player('GuideReader','GuideReader')
        player.prompt_string='&RHP:%h&x'
        output=[]
        session=SimpleNamespace(player=player,send=output.append)
        with patch.object(help_system,'cmd_help') as help_cmd:
            commands.cmd_prompt(session,['help'])
            help_cmd.assert_called_once_with(session,['prompt'])
        self.assertEqual(player.prompt_string,'&RHP:%h&x')

    def test_color_names_render_live_and_codes_remain_copyable(self):
        body=self.page('colors')['body']
        for code,name in (
            ('R','Red'),('G','Green'),('Y','Yellow'),('B','Blue'),
            ('C','Cyan'),('M','Magenta'),('W','White'),('D','Dark gray'),
            ('r','Bright red'),('g','Bright green'),('y','Bright yellow'),
            ('b','Bright blue'),('c','Bright cyan'),('m','Bright magenta'),
            ('w','Bright white'),('d','Bright gray'),('O','Orange'),
        ):
            with self.subTest(color=code):
                self.assertIn('&&'+code,body)  # copyable, literal help code
                self.assertIn('&'+code+name+'&x',body) # real color markup
                visible=colors.render('&'+code+name+'&x',True)
                self.assertIn(colors.ANSI_CODES['&'+code]+name,visible)
        self.assertIn('&&[196]',body)
        self.assertIn('&[196]Bright xterm red&x',body)
        colored=colors.render(body,True)
        self.assertIn('&r',colored) # labeled code remains readable
        self.assertIn('\x1b[22;91mBright red\x1b[0m',colored)
        self.assertIn('\x1b[38;5;196mBright xterm red\x1b[0m',colored)
        uncolored=colors.render(body,False)
        self.assertIn('&r',uncolored)
        self.assertIn('Bright red',uncolored)
        self.assertIn('Example: &&r displays literal &r',uncolored)
        self.assertNotIn('\x1b[',uncolored)

    def test_prompt_examples_only_use_real_tokens(self):
        body=self.page('prompt')['body']
        # Examples are literal on the help screen, but valid when typed.
        example='&RHP:%h/%H &BCH:%c/%C &GST:%s/%S&x'
        player=Player('PromptReader','PromptReader')
        player.health=40
        player.maximum_health=90
        player.chakra=50
        player.maximum_chakra=100
        player.stamina=60
        player.maximum_stamina=120
        player.prompt_string=example
        rendered=prompt.render_prompt(player)
        self.assertIn('HP:40/90',rendered)
        self.assertIn('CH:50/100',rendered)
        self.assertIn('ST:60/120',rendered)
        self.assertIn('%%',body)

    def test_biran_preset_uses_exact_format_and_expands_resources(self):
        expected = "&w|&R%h&w/&196%H&w|&M%c&w/&m%C&w|&c%s&w/&C%S&w|&x"
        self.assertEqual(prompt.PRESETS['biran'], expected)
        player = Player('PresetReader', 'PresetReader')
        player.health = 40
        player.maximum_health = 90
        player.chakra = 50
        player.maximum_chakra = 100
        player.stamina = 60
        player.maximum_stamina = 120
        output = []
        session = SimpleNamespace(player=player, send=output.append)
        commands.cmd_prompt(session, ['biran'])
        self.assertEqual(player.prompt_string, expected)
        self.assertIn("'biran'", output[-1])
        rendered = prompt.render_prompt(player)
        self.assertEqual(rendered, '&w|&R40&w/&19690&w|&M50&w/&m100&w|&c60&w/&C120&w|&x')
        ansi = colors.render(rendered, True)
        self.assertIn('\x1b[38;5;196m90', ansi)
        self.assertIn(colors.ANSI_CODES['&R'] + '40', ansi)
        self.assertEqual(colors.render(rendered, False), '|40/90|50/100|60/120|')

if __name__=='__main__':
    unittest.main()
