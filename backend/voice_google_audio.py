"""Pinned Google audio wire compatibility (Specification §7.1)."""


def audio_input_connection(context):
    return _AudioInputConnection(context)


class _AudioInputConnection:
    def __init__(self, context):
        self.context = context

    async def __aenter__(self):
        self.provider = await self.context.__aenter__()
        self.send = self.provider.send_realtime_input

        async def send_audio(*args, **kwargs):
            blob = kwargs.get("media")
            mime = getattr(blob, "mime_type", None) or ""
            if mime.split(";", 1)[0] == "audio/pcm" and "audio" not in kwargs:
                # Pinned plugin 1.2.9 resamples to 16 kHz. Copy metadata only.
                if mime == "audio/pcm":
                    blob = blob.model_copy(update={"mime_type": "audio/pcm;rate=16000"})
                kwargs = dict(kwargs)
                kwargs.pop("media")
                kwargs["audio"] = blob
            return await self.send(*args, **kwargs)

        self.provider.send_realtime_input = send_audio
        return self.provider

    async def __aexit__(self, *args):
        # Unwind before the inner diagnostics context restores its own method.
        self.provider.send_realtime_input = self.send
        return await self.context.__aexit__(*args)
