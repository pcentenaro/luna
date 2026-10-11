"""Convert internally generated, self-contained SVG to PNG without temporary files."""

import asyncio


async def svg_to_png(svg: str, *, timeout: float = 15) -> bytes:
    """Run librsvg asynchronously. Relative image files are not supported here."""
    if timeout <= 0:
        raise ValueError("The rendering timeout must be positive.")
    payload = svg.encode("utf-8")
    try:
        process = await asyncio.create_subprocess_exec(
            "rsvg-convert", "--format=png",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        raise RuntimeError("Could not start rsvg-convert. Install librsvg2-bin on the bot host.") from error

    try:
        png, errors = await asyncio.wait_for(process.communicate(payload), timeout)
    except (TimeoutError, asyncio.CancelledError) as error:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.communicate()
        if isinstance(error, asyncio.CancelledError):
            raise
        raise RuntimeError(f"SVG rendering exceeded {timeout} seconds.") from error

    if process.returncode != 0:
        detail = errors.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"SVG rendering failed: {detail or process.returncode}")
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("rsvg-convert did not return a PNG image.")
    return png
