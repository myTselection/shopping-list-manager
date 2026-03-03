"""Image handling utilities for Shopping List Manager."""
import logging
import shutil
from pathlib import Path
from typing import Optional

from ..const import (
    IMAGES_LOCAL_DIR,
    LEGACY_IMAGES_LOCAL_DIR,
    LOCAL_IMAGE_URL_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


class ImageHandler:
    """Handle product images with URL and local file support."""
    
    def __init__(self, hass, config_path: str):
        """Initialize image handler.
        
        Args:
            hass: Home Assistant instance
            config_path: Path to HA config directory
        """
        self.hass = hass
        # Images stored in /config/www/images/shopping_list_manager/
        self._local_images_dir = Path(hass.config.path(IMAGES_LOCAL_DIR))
        self._legacy_images_dir = Path(hass.config.path(LEGACY_IMAGES_LOCAL_DIR))
        self._local_images_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_files()
        
        _LOGGER.info("Image directory: %s", self._local_images_dir)

    def _migrate_legacy_files(self) -> None:
        """Move legacy image files to the new standardized directory."""
        if not self._legacy_images_dir.exists() or self._legacy_images_dir == self._local_images_dir:
            return
        for src in self._legacy_images_dir.glob("*"):
            if not src.is_file():
                continue
            dest = self._local_images_dir / src.name
            if dest.exists():
                continue
            try:
                shutil.move(str(src), str(dest))
            except Exception as err:
                _LOGGER.debug("Could not move legacy image %s: %s", src, err)
    
    def get_image_url(self, product_name: str, external_url: Optional[str] = None) -> str:
        """Get image URL for a product.
        
        Priority:
        1. External URL (if provided)
        2. Local file match
        3. Placeholder
        
        Args:
            product_name: Name of product to find image for
            external_url: Optional external image URL
            
        Returns:
            Image URL (external, local, or placeholder)
        """
        # Priority 1: Use external URL if provided
        if external_url:
            return external_url
        
        # Priority 2: Look for local file
        local_url = self._find_local_image(product_name)
        if local_url:
            return local_url
        
        # Priority 3: Placeholder
        return self._get_placeholder_url()
    
    def _find_local_image(self, product_name: str) -> Optional[str]:
        """Find local image file for product.
        
        Searches for files matching product name (case-insensitive).
        Supports: .webp, .jpg, .jpeg, .png
        
        Args:
            product_name: Product name to search for
            
        Returns:
            Local URL if found, None otherwise
        """
        # Normalize product name for filename matching
        normalized_name = product_name.lower().replace(" ", "_")
        
        # Supported extensions
        extensions = [".webp", ".jpg", ".jpeg", ".png"]
        
        for ext in extensions:
            # Check exact match
            image_file = self._local_images_dir / f"{normalized_name}{ext}"
            if image_file.exists():
                return f"{LOCAL_IMAGE_URL_PREFIX}{normalized_name}{ext}"
            
            # Check for files starting with the product name
            for file in self._local_images_dir.glob(f"{normalized_name}*{ext}"):
                return f"{LOCAL_IMAGE_URL_PREFIX}{file.name}"
        
        return None
    
    def _get_placeholder_url(self) -> str:
        """Get placeholder image URL.
        
        Returns:
            URL to placeholder image
        """
        # Use a simple colored placeholder
        # You can replace this with a real placeholder image later
        return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23f0f0f0'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial' font-size='16' fill='%23999'%3ENo Image%3C/text%3E%3C/svg%3E"
    
    def list_available_images(self) -> list:
        """List all available local images.
        
        Returns:
            List of (filename, product_name_guess) tuples
        """
        images = []
        extensions = [".webp", ".jpg", ".jpeg", ".png"]
        
        for ext in extensions:
            for image_file in self._local_images_dir.glob(f"*{ext}"):
                # Guess product name from filename
                product_name = image_file.stem.replace("_", " ").title()
                images.append((image_file.name, product_name))
        
        return sorted(images)
