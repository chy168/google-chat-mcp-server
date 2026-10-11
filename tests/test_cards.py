import asyncio
import unittest
from unittest.mock import MagicMock, patch

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


REPORT_CARD_MESSAGE = {
    'cardsV2': [{'card': {
        'header': {'title': 'Weekly check', 'subtitle': 'All green', 'imageUrl': 'https://example.com/i.png'},
        'sections': [
            {'header': 'Indicators', 'collapsible': True, 'widgets': [
                {'decoratedText': {'topLabel': 'Total', 'text': '1 000', 'bottomLabel': 'within band',
                                   'startIcon': {'knownIcon': 'STAR'}}},
                {'decoratedText': {'text': 'Report', 'onClick': {'openLink': {'url': 'https://example.com/r'}}}},
                {'textParagraph': {'text': '<i>see</i> <s>old</s> <a href="https://example.com/doc">doc</a> <font color="#f00">red</font>'}},
            ]},
            {'widgets': [
                {'columns': {'columnItems': [
                    {'widgets': [{'textParagraph': {'text': '<b>Run</b>'}}]},
                    {'widgets': [{'textParagraph': {'text': 'r-1'}}]},
                ]}},
                {'divider': {}},
                {'someFutureWidget': {'text': 'kept by fallback'}},
            ]},
        ],
    }}],
}


class ExtractCardsTextTest(unittest.TestCase):
    def test_renders_cards_v2_as_markdown(self):
        self.assertEqual(
            extract_cards_text(CI_CARD_MESSAGE),
            '## ❌ my-pipeline #42\n\n'
            '_Build failed_\n\n'
            '**Step "deploy" failed.**\nSee the logs.\n'
            '- **Duration** : 11 sec\n'
            '[Open build](https://ci.example.com/42)',
        )

    def test_sections_labels_links_columns_and_fallback(self):
        self.assertEqual(
            extract_cards_text(REPORT_CARD_MESSAGE),
            '## Weekly check\n\n'
            '_All green_\n\n'
            '### Indicators\n\n'
            '- **Total** : 1 000 · _within band_\n'
            '- [Report](https://example.com/r)\n'
            '_see_ ~~old~~ [doc](https://example.com/doc) red\n\n'
            '- **Run**\n'
            '- r-1\n'
            '---\n'
            'kept by fallback',
        )

    def test_reads_legacy_cards(self):
        self.assertEqual(extract_cards_text(LEGACY_CARD_MESSAGE), 'Status\nOK')

    def test_plain_text_message_has_no_card_text(self):
        self.assertIsNone(extract_cards_text({'text': 'hello'}))

    def test_icons_and_header_images_are_not_rendered(self):
        rendered = extract_cards_text(REPORT_CARD_MESSAGE)
        self.assertNotIn('i.png', rendered)
        self.assertNotIn('STAR', rendered)


class ListSpaceMessagesTest(unittest.TestCase):
    def list_messages(self, api_messages):
        service = MagicMock()
        service.spaces().messages().list().execute.return_value = {'messages': api_messages}
        with patch.object(google_chat, 'get_credentials', return_value=object()), \
                patch.object(google_chat, 'build', return_value=service), \
                patch.object(google_chat, 'get_user_display_name', return_value='CI bot'):
            return asyncio.run(google_chat.list_space_messages('spaces/X'))

    def test_card_message_gets_a_cards_field(self):
        api_message = dict(CI_CARD_MESSAGE, sender={'name': 'users/1', 'type': 'BOT'},
                           createTime='2026-01-01T00:00:00Z', thread={'name': 'spaces/X/threads/T'})
        [msg] = self.list_messages([api_message])
        self.assertEqual(msg['sender'], 'CI bot')
        self.assertIsNone(msg['text'])
        self.assertEqual(msg['cards'], extract_cards_text(CI_CARD_MESSAGE))

    def test_plain_message_has_no_cards_field(self):
        [msg] = self.list_messages([{'text': 'hello', 'sender': {'name': 'users/2'}}])
        self.assertEqual(msg['text'], 'hello')
        self.assertNotIn('cards', msg)


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
