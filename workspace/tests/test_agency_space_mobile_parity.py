"""API parity: mobile detail actions must have the same permission/state semantics as Django."""
from workspace.models import AgencySpaceItem
from workspace.services.agency_space_moderation import (
    hide_space_item_public,
    restore_space_item_moderation,
)
from workspace.services.agency_space_publish import publish_property
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase


class AgencySpaceMobileActionParityTests(AgencySpaceTestBase):
    def test_manager_can_restore_only_a_hidden_publication(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        active = serialize_space_item(item, self.owner, detail=True)
        self.assertTrue(active['can_moderate'])
        self.assertFalse(active['can_restore'])

        hide_space_item_public(self.owner, item.pk)
        item.refresh_from_db()
        hidden = serialize_space_item(item, self.owner, detail=True)
        self.assertFalse(hidden['can_moderate'])
        self.assertTrue(hidden['can_restore'])

        # Hidden content remains inaccessible to other advisors.
        self.assertIsNone(serialize_space_item(item, self.advisor2, detail=True))

        restore_space_item_moderation(self.owner, item.pk)
        item.refresh_from_db()
        restored = serialize_space_item(item, self.owner, detail=True)
        self.assertTrue(restored['can_moderate'])
        self.assertFalse(restored['can_restore'])

    def test_regular_advisor_cannot_restore_managers_hidden_item(self):
        item = publish_property(
            self.advisor, self._prop().pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        hide_space_item_public(self.owner, item.pk)
        item.refresh_from_db()
        publisher_view = serialize_space_item(item, self.advisor, detail=True)
        self.assertIsNotNone(publisher_view)
        self.assertFalse(publisher_view['can_moderate'])
        self.assertFalse(publisher_view['can_restore'])
