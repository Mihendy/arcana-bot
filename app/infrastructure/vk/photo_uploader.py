"""VK photo upload helper.

VK does not accept external URLs for photos — images must be uploaded to VK
servers first and then referenced by their media attachment string
(``photo{owner_id}_{media_id}``).
"""

from __future__ import annotations

from io import BytesIO

from vkbottle import API


class VKPhotoUploader:
    """Uploads a photo to a VK group's message upload server.

    Returns the attachment string accepted by ``messages.send``.
    """

    def __init__(self, api: API, group_id: int) -> None:
        self._api = api
        self._group_id = group_id

    async def upload_message_photo(self, image: BytesIO, filename: str = "image.png") -> str:
        """Upload *image* and return ``photo{owner}_{id}`` attachment string.

        Args:
            image: In-memory image bytes (PNG/JPEG).
            filename: Filename hint for the upload server.

        Returns:
            str: VK attachment string, e.g. ``photo-12345_67890``.

        Raises:
            RuntimeError: If upload or save fails.
        """
        upload_server = await self._api.photos.get_messages_upload_server(
            peer_id=0
        )
        upload_url: str = upload_server.upload_url

        import httpx
        image.seek(0)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                files={"photo": (filename, image, "image/png")},
            )
            response.raise_for_status()
            data = response.json()

        saved = await self._api.photos.save_messages_photo(
            photo=data["photo"],
            server=data["server"],
            hash=data["hash"],
        )
        if not saved:
            raise RuntimeError("VK photos.saveMessagesPhoto returned empty list")

        photo = saved[0]
        return f"photo{photo.owner_id}_{photo.id}"
