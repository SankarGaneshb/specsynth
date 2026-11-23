"""
Assembles captured frames into a smooth, optimized animated GIF demo for GitHub README.
"""

from pathlib import Path
from PIL import Image

def main():
    root = Path(__file__).resolve().parent.parent
    frames_dir = root / ".tmp_frames"
    assets_dir = root / "assets"
    docs_assets_dir = root / "docs" / "assets"
    artifact_dir = Path("C:/Users/bsank/.gemini/antigravity/brain/11b6a273-51ad-4a74-9e31-731fe71e6e4f")

    frame_files = sorted(frames_dir.glob("frame_*.png"))
    if not frame_files:
        print("[ERROR] No frame images found in", frames_dir)
        return

    print(f"Loading {len(frame_files)} frames for GIF assembly...")
    images = []
    target_width = 1000  # High-definition yet web-optimized for GitHub README

    # Frame durations in milliseconds: linger on important views, faster on slider sweeps
    # Total frames: 13
    durations = [
        1800,  # Frame 1: Landing Sky Canvas
        1500,  # Frame 2: Galaxy selection & Sidebar open
        1800,  # Frame 3: Photometry Bar
        450,   # Frame 4: z = 1.80
        450,   # Frame 5: z = 2.80
        450,   # Frame 6: z = 3.80
        1500,  # Frame 7: z = 4.50 (Lyman dropout)
        1800,  # Frame 8: Updated Photometry at z = 4.50
        1500,  # Frame 9: Color-Color Plot
        600,   # Frame 10: Av = 1.50 mag
        1500,  # Frame 11: Av = 2.50 mag
        2200,  # Frame 12: JWST Proposal Modal
        2000,  # Frame 13: Dataset switch to TNG-100
    ]

    for f in frame_files:
        im = Image.open(f).convert("RGB")
        w, h = im.size
        target_height = int(h * (target_width / w))
        im_resized = im.resize((target_width, target_height), Image.Resampling.LANCZOS)
        # Convert to adaptive 128-color palette with dithering for compact GIF size
        im_quant = im_resized.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
        images.append(im_quant)

    # Pad durations if frames count differs
    while len(durations) < len(images):
        durations.append(1000)
    durations = durations[:len(images)]

    # Target output paths
    out_paths = [
        assets_dir / "perandam_walkthrough.gif",
        docs_assets_dir / "perandam_walkthrough.gif",
        artifact_dir / "perandam_walkthrough.gif",
    ]

    print("Generating optimized animated GIF...")
    first_image = images[0]
    for out_p in out_paths:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        first_image.save(
            out_p,
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            optimize=True,
        )
        size_kb = out_p.stat().st_size / 1024
        print(f"  ✓ Saved: {out_p} ({size_kb:.1f} KB)")

    print("\n🎉 Animated walkthrough GIF generated successfully!")

if __name__ == "__main__":
    main()
