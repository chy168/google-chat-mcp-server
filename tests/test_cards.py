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
            '- r-1\n\n'
            '---\n\n'
            'kept by fallback',
        )

    def test_reads_legacy_cards(self):
        self.assertEqual(extract_cards_text(LEGACY_CARD_MESSAGE), '- **Status** : OK')

    def test_legacy_cards_keep_headers_and_button_links(self):
        message = {'cards': [{
            'header': {'title': 'Nightly', 'subtitle': 'done'},
            'sections': [{'header': 'Result', 'widgets': [
                {'keyValue': {'topLabel': 'Status', 'content': 'OK', 'onClick': {'openLink': {'url': 'https://x/s'}}}},
                {'textParagraph': {'text': '<b>All</b> good'}},
                {'buttons': [
                    {'textButton': {'text': 'Logs', 'onClick': {'openLink': {'url': 'https://x/l'}}}},
                    {'imageButton': {'icon': 'DESCRIPTION', 'name': 'Report', 'onClick': {'openLink': {'url': 'https://x/r'}}}},
                ]},
            ]}],
        }]}
        self.assertEqual(
            extract_cards_text(message),
            '## Nightly\n\n_done_\n\n### Result\n\n'
            '- **Status** : [OK](https://x/s)\n**All** good\n[Logs](https://x/l) · [Report](https://x/r)',
        )

    def test_plain_text_message_has_no_card_text(self):
        self.assertIsNone(extract_cards_text({'text': 'hello'}))

    def test_column_cells_get_a_single_list_prefix(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [{'columns': {'columnItems': [
            {'widgets': [{'decoratedText': {'topLabel': 'Env', 'text': 'prod'}}]},
        ]}}]}]}}]}
        self.assertEqual(extract_cards_text(message), '- **Env** : prod')

    def test_decorated_text_button_keeps_its_link(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [{'decoratedText': {
            'text': 'Job', 'button': {'text': 'Logs', 'onClick': {'openLink': {'url': 'https://ci.example.com/42/log'}}},
        }}]}]}}]}
        self.assertEqual(extract_cards_text(message), '- Job · [Logs](https://ci.example.com/42/log)')

    def test_single_quoted_href_keeps_its_link(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [
            {'textParagraph': {'text': "<a href='https://example.com/y'>doc</a>"}},
        ]}]}}]}
        self.assertEqual(extract_cards_text(message), '[doc](https://example.com/y)')

    def test_divider_after_a_paragraph_stays_a_rule(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [
            {'textParagraph': {'text': 'Summary'}}, {'divider': {}}, {'textParagraph': {'text': 'After'}},
        ]}]}}]}
        self.assertEqual(extract_cards_text(message), 'Summary\n\n---\n\nAfter')

    def test_tags_with_attributes_keep_their_formatting_balanced(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [
            {'textParagraph': {'text': '<b class="x">bold</b > <i style="a">it</i> <font color="#f00">red</font> <span>s</span>'}},
        ]}]}}]}
        self.assertEqual(extract_cards_text(message), '**bold** _it_ red s')

    def test_icon_only_buttons_keep_their_link(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [
            {'buttonList': {'buttons': [
                {'icon': {'knownIcon': 'OPEN_IN_NEW'}, 'altText': 'Open build', 'onClick': {'openLink': {'url': 'https://x/1'}}},
                {'icon': {'knownIcon': 'STAR', 'altText': 'Star it'}, 'onClick': {'openLink': {'url': 'https://x/2'}}},
                {'icon': {'knownIcon': 'BOOKMARK'}, 'onClick': {'openLink': {'url': 'https://x/3'}}},
            ]}},
            {'decoratedText': {'text': 'Job', 'button': {'icon': {'knownIcon': 'OPEN_IN_NEW'}, 'altText': 'Logs',
                                                         'onClick': {'openLink': {'url': 'https://x/l'}}}}},
        ]}]}}]}
        self.assertEqual(
            extract_cards_text(message),
            '[Open build](https://x/1) · [Star it](https://x/2) · <https://x/3>\n- Job · [Logs](https://x/l)',
        )

    def test_chips_are_rendered_like_buttons(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [
            {'chipList': {'chips': [{'label': 'prod', 'onClick': {'openLink': {'url': 'https://x/p'}}}, {'label': 'eu-west'}]}},
        ]}]}}]}
        self.assertEqual(extract_cards_text(message), '[prod](https://x/p) · eu-west')

    def test_fallback_reads_label_fields(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [{'textInput': {'label': 'Ticket number'}}]}]}}]}
        self.assertEqual(extract_cards_text(message), 'Ticket number')

    def test_clickable_decorated_text_with_a_link_does_not_nest_links(self):
        message = {'cardsV2': [{'card': {'sections': [{'widgets': [{'decoratedText': {
            'text': '<a href="https://x/doc">doc</a>', 'onClick': {'openLink': {'url': 'https://x/b'}},
        }}]}]}}]}
        self.assertEqual(extract_cards_text(message), '- [doc](https://x/doc) · <https://x/b>')

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

    def test_card_message_gets_a_cards_text_field(self):
        api_message = dict(CI_CARD_MESSAGE, sender={'name': 'users/1', 'type': 'BOT'},
                           createTime='2026-01-01T00:00:00Z', thread={'name': 'spaces/X/threads/T'})
        [msg] = self.list_messages([api_message])
        self.assertEqual(msg['sender'], 'CI bot')
        self.assertIsNone(msg['text'])
        self.assertEqual(msg['cards_text'], extract_cards_text(CI_CARD_MESSAGE))

    def test_plain_message_has_no_cards_text_field(self):
        [msg] = self.list_messages([{'text': 'hello', 'sender': {'name': 'users/2'}}])
        self.assertEqual(msg['text'], 'hello')
        self.assertNotIn('cards_text', msg)

    def test_raw_mode_keeps_the_api_message_and_adds_cards_text(self):
        with patch.object(google_chat, 'SAVE_TOKEN_MODE', False):
            [msg] = self.list_messages([LEGACY_CARD_MESSAGE])
        self.assertEqual(msg['cards'], LEGACY_CARD_MESSAGE['cards'])
        self.assertEqual(msg['cards_text'], '- **Status** : OK')


class SearchMessagesTest(unittest.TestCase):
    def search(self, api_messages, query, save_token_mode=True):
        service = MagicMock()
        service.spaces().messages().list().execute.return_value = {'messages': api_messages}
        with patch.object(google_chat, 'get_credentials', return_value=object()), \
                patch.object(google_chat, 'build', return_value=service), \
                patch.object(google_chat, 'get_user_display_name', return_value='CI bot'), \
                patch.object(google_chat, 'SAVE_TOKEN_MODE', save_token_mode):
            return asyncio.run(google_chat.search_messages('spaces/X', query))

    def test_matches_card_text_when_text_is_empty(self):
        [msg] = self.search([CI_CARD_MESSAGE], 'BUILD FAILED')
        self.assertEqual(msg['cards_text'], extract_cards_text(CI_CARD_MESSAGE))

    def test_matches_across_formatting_added_by_the_renderer(self):
        # Rendered as '**Step "deploy" failed.**' and '- **Duration** : 11 sec'.
        self.assertEqual(len(self.search([CI_CARD_MESSAGE], 'step "deploy" failed')), 1)
        self.assertEqual(len(self.search([CI_CARD_MESSAGE], 'duration 11 sec')), 1)

    def test_matches_link_urls(self):
        self.assertEqual(len(self.search([CI_CARD_MESSAGE], 'ci.example.com/42')), 1)

    def test_raw_mode_returns_api_messages(self):
        self.assertEqual(self.search([CI_CARD_MESSAGE], 'deploy', save_token_mode=False)[0]['cardsV2'],
                         CI_CARD_MESSAGE['cardsV2'])

    def test_matches_raw_messages_with_legacy_cards(self):
        # With save-token mode off, messages come straight from the API, where `cards` is a list.
        [msg] = self.search([LEGACY_CARD_MESSAGE], 'ok', save_token_mode=False)
        self.assertEqual(msg['cards'], LEGACY_CARD_MESSAGE['cards'])

    def test_still_matches_plain_text_and_skips_misses(self):
        hit, miss = {'text': 'deploy done'}, {'text': 'unrelated'}
        self.assertEqual([m['text'] for m in self.search([hit, miss], 'deploy')], ['deploy done'])


if __name__ == '__main__':
    unittest.main()
