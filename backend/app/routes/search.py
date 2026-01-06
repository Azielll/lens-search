from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/search")
async def search_images(query: str, top_k: int = 10):
    """
    Search for images based on a text query using CLIP embeddings.
    
    Args:
        query: Text query to search for
        top_k: Number of top results to return (default: 10)
    
    Returns:
        List of image results with similarity scores
    """
    # TODO: Implement search logic using CLIP model and embeddings
    # This will be implemented when services are created
    raise HTTPException(
        status_code=501,
        detail="Search endpoint not yet implemented. CLIP model and embeddings need to be set up."
    )

