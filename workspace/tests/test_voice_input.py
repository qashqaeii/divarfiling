from django import forms

from django.test import SimpleTestCase

from workspace.voice_input import field_allows_workspace_voice


class VoiceInputEligibilityTests(SimpleTestCase):
    def _bound(self, name, widget):
        form = forms.Form()
        form.fields[name] = forms.Field(widget=widget, required=False)
        return form[name]

    def test_textarea_note_allowed(self):
        field = self._bound('note', forms.Textarea())
        self.assertTrue(field_allows_workspace_voice(field))

    def test_textarea_unknown_name_denied(self):
        field = self._bound('trigger_statuses', forms.Textarea())
        self.assertFalse(field_allows_workspace_voice(field))

    def test_search_query_denied(self):
        field = self._bound('q', forms.TextInput())
        self.assertFalse(field_allows_workspace_voice(field))

    def test_explicit_off_denied(self):
        field = self._bound('body', forms.Textarea(attrs={'data-voice-input': 'off'}))
        self.assertFalse(field_allows_workspace_voice(field))

    def test_title_text_allowed(self):
        field = self._bound('title', forms.TextInput())
        self.assertTrue(field_allows_workspace_voice(field))

    def test_template_name_off_via_attr(self):
        field = self._bound('name', forms.TextInput(attrs={'data-voice-input': 'off'}))
        self.assertFalse(field_allows_workspace_voice(field))
