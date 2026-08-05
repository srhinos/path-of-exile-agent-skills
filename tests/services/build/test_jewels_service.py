from __future__ import annotations

import pytest

from poe.exceptions import BuildValidationError, SlotError
from poe.services.build.jewels_service import JewelsService
from tests.conftest import PoBXmlBuilder


class TestJewelsService:
    def test_list_jewels(self, builds_dir):
        svc = JewelsService()
        result = svc.list_jewels("TestBuild")
        assert result.jewels is not None


class TestJewelsServiceAdditional:
    def test_list_jewels_with_items(self, rich_build):
        svc = JewelsService()
        r = svc.list_jewels("ignored", file_path=str(rich_build))
        assert hasattr(r, "jewels")
        assert hasattr(r, "cluster_jewels")


class TestJewelsServiceCoverage:
    def test_list_with_jewels(self, tmp_path):
        builder = PoBXmlBuilder(tmp_path)
        builder.with_class("Witch")
        builder.with_tree_spec("Main", [100], sockets=[(26725, 1)])
        builder.with_item("Jewel 1", name="Cobalt Jewel", base_type="Cobalt Jewel")
        builder.with_item(
            "Jewel 2",
            name="Large Cluster Jewel",
            base_type="Large Cluster Jewel",
        )
        path = builder.write("jewels_test.xml")
        svc = JewelsService()
        result = svc.list_jewels("ignored", file_path=str(path))
        assert len(result.jewels) >= 1 or len(result.cluster_jewels) >= 1


class TestJewelsCRUD:
    def test_add_jewel(self, rich_build):
        svc = JewelsService()
        r = svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_remove_jewel_by_slot(self, rich_build):
        svc = JewelsService()
        svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        r = svc.remove_jewel("ignored", slot="Jewel 1", file_path=str(rich_build))
        assert r.status == "ok"

    def test_remove_jewel_no_target(self, rich_build):
        svc = JewelsService()
        with pytest.raises(BuildValidationError):
            svc.remove_jewel("ignored", file_path=str(rich_build))

    def test_remove_jewel_not_found(self, rich_build):
        svc = JewelsService()
        with pytest.raises(SlotError):
            svc.remove_jewel("ignored", item_id=9999, file_path=str(rich_build))

    def test_socket_jewel(self, rich_build):
        svc = JewelsService()
        svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        from poe.services.build.build_service import BuildService

        _, build = BuildService().load("ignored", file_path=str(rich_build))
        jewel_id = next(i.id for i in build.items if "Jewel" in i.base_type)
        r = svc.socket_jewel(
            "ignored",
            item_id=jewel_id,
            node_id=26725,
            file_path=str(rich_build),
        )
        assert r.status == "ok"

    def test_socket_jewel_invalid_item(self, rich_build):
        svc = JewelsService()
        with pytest.raises(SlotError):
            svc.socket_jewel(
                "ignored",
                item_id=9999,
                node_id=26725,
                file_path=str(rich_build),
            )

    def test_unsocket_jewel(self, rich_build):
        svc = JewelsService()
        r = svc.unsocket_jewel("ignored", node_id=26725, file_path=str(rich_build))
        assert r.status == "ok"

    def test_unsocket_jewel_not_found(self, rich_build):
        svc = JewelsService()
        with pytest.raises(SlotError, match="not found"):
            svc.unsocket_jewel(
                "ignored",
                node_id=99999,
                file_path=str(rich_build),
            )

    def test_unsocket_jewel_no_args(self, rich_build):
        svc = JewelsService()
        with pytest.raises(BuildValidationError):
            svc.unsocket_jewel("ignored", file_path=str(rich_build))


class TestJewelsAddInvariants:
    @pytest.mark.parametrize(
        "base",
        [
            "Cobalt Jewel",
            "Crimson Jewel",
            "Viridian Jewel",
            "Prismatic Jewel",
            "Murderous Eye Jewel",
            "Searching Eye Jewel",
            "Hypnotic Eye Jewel",
            "Ghastly Eye Jewel",
            "Large Cluster Jewel",
            "Medium Cluster Jewel",
            "Small Cluster Jewel",
            "Timeless Jewel",
        ],
    )
    def test_add_each_jewel_base(self, rich_build, base):
        svc = JewelsService()
        result = svc.add_jewel(
            "ignored",
            base=base,
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        assert result.status == "ok"

    def test_add_jewel_assigns_unique_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = JewelsService()
        _, before = BuildService().load("ignored", file_path=str(rich_build))
        before_ids = {i.id for i in before.items}
        result = svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        assert result.item_id not in before_ids


class TestJewelsRemoveInvariants:
    def test_remove_clears_socket_binding(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = JewelsService()
        svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        jewel = next(i for i in build.items if i.base_type == "Cobalt Jewel")
        svc.socket_jewel(
            "ignored",
            item_id=jewel.id,
            node_id=26725,
            file_path=str(rich_build),
        )
        svc.remove_jewel("ignored", item_id=jewel.id, file_path=str(rich_build))
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        spec = after.get_active_spec()
        assert all(s.item_id != jewel.id for s in spec.sockets)
        assert not any(i.id == jewel.id for i in after.items)


class TestSocketJewelOverrides:
    def test_socket_jewel_overrides_existing_socket(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = JewelsService()
        svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        jewel = next(i for i in build.items if i.base_type == "Cobalt Jewel")
        svc.socket_jewel(
            "ignored",
            item_id=jewel.id,
            node_id=26725,
            file_path=str(rich_build),
        )
        svc.socket_jewel(
            "ignored",
            item_id=jewel.id,
            node_id=11111,
            file_path=str(rich_build),
        )
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        spec = after.get_active_spec()
        bindings = [s for s in spec.sockets if s.item_id == jewel.id]
        assert len(bindings) == 1
        assert bindings[0].node_id == 11111


class TestUnsocketByItemId:
    def test_unsocket_by_item_id(self, rich_build):
        from poe.services.build.build_service import BuildService

        svc = JewelsService()
        svc.add_jewel(
            "ignored",
            base="Cobalt Jewel",
            slot="Jewel 1",
            file_path=str(rich_build),
        )
        _, build = BuildService().load("ignored", file_path=str(rich_build))
        jewel = next(i for i in build.items if i.base_type == "Cobalt Jewel")
        svc.socket_jewel(
            "ignored",
            item_id=jewel.id,
            node_id=44444,
            file_path=str(rich_build),
        )
        result = svc.unsocket_jewel(
            "ignored",
            item_id=jewel.id,
            file_path=str(rich_build),
        )
        assert result.status == "ok"
        _, after = BuildService().load("ignored", file_path=str(rich_build))
        spec = after.get_active_spec()
        assert all(s.item_id != jewel.id for s in spec.sockets)


class TestSocketJewelNoActiveSpec:
    def test_socket_no_spec(self, tmp_path):
        from tests.conftest import PoBXmlBuilder

        builder = PoBXmlBuilder(tmp_path)
        builder.with_class("Witch")
        path = builder.write("nospec.xml")
        from poe.services.build.build_service import BuildService
        from poe.services.build.xml.parser import parse_build_file
        from poe.services.build.xml.writer import write_build_file

        b = parse_build_file(path)
        b.specs = []
        write_build_file(b, path)
        svc = JewelsService()
        b2 = BuildService()
        _, build = b2.load("ignored", file_path=str(path))
        if build.items:
            with pytest.raises(BuildValidationError):
                svc.socket_jewel(
                    "ignored",
                    item_id=build.items[0].id,
                    node_id=1,
                    file_path=str(path),
                )
