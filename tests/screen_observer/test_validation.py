from PIL import Image, ImageDraw

from screen_observer.validation import validate_image


def _synthetic_chart() -> Image.Image:
    image = Image.new("RGB", (900, 500), "white")
    draw = ImageDraw.Draw(image)

    for y in range(80, 460, 60):
        draw.line((40, y, 860, y), fill=(215, 215, 215), width=1)
    for x in range(80, 860, 100):
        draw.line((x, 60, x, 460), fill=(225, 225, 225), width=1)

    for left, top, right, bottom, color in [
        (120, 320, 145, 380, (30, 170, 70)),
        (190, 250, 215, 330, (210, 45, 55)),
        (260, 280, 285, 350, (30, 170, 70)),
        (330, 220, 355, 300, (210, 45, 55)),
        (400, 250, 425, 325, (30, 170, 70)),
        (470, 180, 495, 270, (30, 170, 70)),
        (540, 210, 565, 290, (210, 45, 55)),
        (610, 160, 635, 250, (30, 170, 70)),
    ]:
        center = (left + right) // 2
        draw.line((center, top - 18, center, bottom + 18), fill=color, width=3)
        draw.rectangle((left, top, right, bottom), fill=color)

    return image


def test_validate_image_returns_structured_report():
    report = validate_image(_synthetic_chart(), source="synthetic")
    assert report["source"] == "synthetic"
    assert report["image"] == {"width": 900, "height": 500}
    assert report["chart"]["detected"] is True
    assert report["candles"]["total"] >= 5
    assert 0.0 <= report["candles"]["confidence"] <= 1.0
