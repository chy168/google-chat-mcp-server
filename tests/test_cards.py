import asyncio
import unittest
from unittest.mock import patch

import google_chat
from google_chat import extract_cards_text

CI_CARD_MESSAGE = {
    'text': None,
    'cardsV2': [{
        'cardId': 'build',
        'card': {
            'header': {'title': '❌ my-pipeline #42', 'subtitle': 'Build failed'},
            'sections': [{
                'widgets': [
                    {'textParagraph': {'text': '<b>Step &quot;deploy&quot; failed.</b><br/>See the logs.'}},
                    {'decoratedText': {'topLabel': 'Duration', 'text': '11 sec'}},
                    {'buttonList': {'buttons': [{'text': 'Open build', 'onClick': {'openLink': {'url': 'https://ci.example.com/42'}}}]}},
                ],
            }],
        },
    }],
}

LEGACY_CARD_MESSAGE = {
    'cards': [{'sections': [{'widgets': [{'keyValue': {'topLabel': 'Status', 'content': 'OK'}}]}]}],
}


class ExtractCardsTextTest(unittest.TestCase):
    def test_flattens_cards_v2_header_widgets_and_buttons(self):
        self.assertEqual(
            extract_cards_text(CI_CARD_MESSAGE),
            '❌ my-pipeline #42\nBuild failed\nStep "deploy" failed.\nSee the logs.\nDuration\n11 sec\nOpen build',
        )

    def test_reads_legacy_cards(self):
        self.assertEqual(extract_cards_text(LEGACY_CARD_MESSAGE), 'Status\nOK')

    def test_plain_text_message_has_no_card_text(self):
        self.assertIsNone(extract_cards_text({'text': 'hello'}))

    def test_urls_are_not_mistaken_for_text(self):
        self.assertNotIn('https://', extract_cards_text(CI_CARD_MESSAGE))


class SearchMessagesTest(unittest.TestCase):
    def search(self, messages, query):
        async def fake_list(*_args, **_kwargs):
            return messages
        with patch.object(google_chat, 'list_space_messages', fake_list):
            return asyncio.run(google_chat.search_messages('spaces/X', query))

    def test_matches_card_text_when_text_is_empty(self):
        msg = {'text': None, 'cards': extract_cards_text(CI_CARD_MESSAGE)}
        self.assertEqual(self.search([msg], 'BUILD FAILED'), [msg])

    def test_matches_raw_messages_without_cards_field(self):
        self.assertEqual(self.search([CI_CARD_MESSAGE], 'deploy'), [CI_CARD_MESSAGE])

    def test_still_matches_plain_text_and_skips_misses(self):
        hit, miss = {'text': 'deploy done'}, {'text': 'unrelated'}
        self.assertEqual(self.search([hit, miss], 'deploy'), [hit])


if __name__ == '__main__':
    unittest.main()
