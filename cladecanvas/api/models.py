from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class NodeMetadata(BaseModel):
    ott_id: int
    common_name: Optional[str]
    description: Optional[str]
    full_description: Optional[str]
    image_url: Optional[str]
    wiki_page_url: Optional[str]
    rank: Optional[str] = None
    enriched_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class TreeNode(BaseModel):
    ott_id: int
    name: str
    parent_ott_id: Optional[int]
    child_count: Optional[int]
    has_metadata: Optional[bool]

    model_config = ConfigDict(from_attributes=True)

class LineageResponse(BaseModel):
    lineage: List[TreeNode]

class SubtreeResponse(BaseModel):
    nodes: List[TreeNode]
