import pytest
from cladecanvas.api.models import TreeNode, NodeMetadata, LineageResponse, SubtreeResponse


class TestTreeNode:
    def test_full_construction(self):
        node = TreeNode(
            node_id="ott691846",
            ott_id=691846,
            name="Metazoa",
            parent_node_id=None,
            child_count=12,
            has_metadata=True,
            num_tips=1700000,
            display_name=None,
        )
        assert node.node_id == "ott691846"
        assert node.num_tips == 1700000

    def test_optional_fields_as_none(self):
        node = TreeNode(
            node_id="mrcaott42ott150",
            name="Bilateria + Cnidaria",
            child_count=None,
            has_metadata=None,
        )
        assert node.ott_id is None
        assert node.parent_node_id is None
        assert node.display_name is None

    def test_from_dict(self):
        """model_validate should work with dict (simulating DB row)."""
        data = {
            "node_id": "ott117569",
            "ott_id": 117569,
            "name": "Bilateria",
            "parent_node_id": "mrcaott42ott150",
            "child_count": 5,
            "has_metadata": True,
            "num_tips": 1464294,
            "display_name": None,
        }
        node = TreeNode.model_validate(data)
        assert node.name == "Bilateria"
        assert node.has_metadata is True

    def test_synthetic_mrca_node(self):
        """MRCA nodes have no ott_id and may have display_name."""
        node = TreeNode(
            node_id="mrcaott42ott3989",
            name="Bilateria + Porifera",
            child_count=None,
            has_metadata=None,
            display_name="Epitheliozoa",
        )
        assert node.ott_id is None
        assert node.display_name == "Epitheliozoa"

    def test_missing_required_field_raises(self):
        """node_id and name are required."""
        with pytest.raises(Exception):
            TreeNode(node_id="ott1", child_count=None, has_metadata=None)


class TestNodeMetadata:
    def test_minimal(self):
        meta = NodeMetadata(
            node_id="ott117569",
            common_name=None,
            description=None,
            full_description=None,
            image_url=None,
            wiki_page_url=None,
        )
        assert meta.node_id == "ott117569"
        assert meta.enriched_score is None

    def test_fully_enriched(self):
        meta = NodeMetadata(
            node_id="ott117569",
            ott_id=117569,
            common_name="Bilateria",
            description="animals with bilateral symmetry",
            full_description="<p>Bilateria are...</p>",
            image_url="http://example.com/img.jpg",
            wiki_page_url="https://en.wikipedia.org/wiki/Bilateria",
            rank="clade",
            enriched_score=1.0,
        )
        assert meta.enriched_score == 1.0
        assert meta.rank == "clade"

    def test_mrca_node_no_ott_id(self):
        """MRCA nodes have null ott_id in metadata."""
        meta = NodeMetadata(
            node_id="mrcaott42ott150",
            ott_id=None,
            common_name="Planulozoa",
            description="clade of animals",
            full_description="<p>Planulozoa is...</p>",
            image_url=None,
            wiki_page_url="https://en.wikipedia.org/wiki/Planulozoa",
        )
        assert meta.ott_id is None
        assert meta.common_name == "Planulozoa"


class TestResponseModels:
    def test_lineage_empty(self):
        resp = LineageResponse(lineage=[])
        assert resp.lineage == []

    def test_lineage_populated(self):
        nodes = [
            TreeNode(node_id="ott691846", name="Metazoa", child_count=12, has_metadata=True),
            TreeNode(node_id="ott117569", name="Bilateria", child_count=5, has_metadata=True,
                     parent_node_id="mrcaott42ott150"),
        ]
        resp = LineageResponse(lineage=nodes)
        assert len(resp.lineage) == 2

    def test_subtree_response(self):
        resp = SubtreeResponse(nodes=[])
        assert resp.nodes == []
