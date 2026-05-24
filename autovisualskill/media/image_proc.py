from PIL import Image


def get_image_info(path: str) -> dict:
    """Return {"width": int, "height": int, "format": str}."""
    with Image.open(path) as img:
        return {"width": img.width, "height": img.height, "format": img.format}


def crop_image(
    path: str,
    left: int,
    top: int,
    right: int,
    bottom: int,
    output_path: str,
) -> str:
    """Crop an image, save it, and return output_path."""
    with Image.open(path) as img:
        cropped = img.crop((left, top, right, bottom))
        cropped.save(output_path)
    return output_path


def prepare_image_for_llm(path: str, output_path: str, max_side: int = 1600) -> str:
    """Normalize and downscale an image for multimodal LLM calls."""
    with Image.open(path) as img:
        img.load()
        if img.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", img.size, "white")
            alpha = img.getchannel("A") if img.mode == "RGBA" else img.getchannel(1)
            background.paste(img.convert("RGBA"), mask=alpha)
            img = background
        else:
            img = img.convert("RGB")

        width, height = img.size
        scale = min(max_side / max(width, height), 1.0)
        if scale < 1.0:
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        img.save(output_path, format="PNG", optimize=True)
    return output_path
