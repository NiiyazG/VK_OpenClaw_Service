from vk_openclaw_service.domain.attachments import (
    AttachmentCandidate,
    AttachmentPolicy,
    AttachmentRejection,
    AttachmentSource,
    validate_attachment,
)


def test_photo_is_accepted_by_content_type_even_if_name_has_vk_size_suffix() -> None:
    candidate = AttachmentCandidate(
        source=AttachmentSource.PHOTO,
        original_name="photo_123.z",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    policy = AttachmentPolicy(
        allowed_mime={"image/jpeg", "application/pdf"},
        max_file_mb=10,
    )

    accepted = validate_attachment(candidate, policy)

    assert accepted.mime == "image/jpeg"
    assert accepted.safe_name.endswith(".jpg")


def test_document_is_accepted_when_mime_and_size_are_allowed() -> None:
    candidate = AttachmentCandidate(
        source=AttachmentSource.DOC,
        original_name="report.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    policy = AttachmentPolicy(
        allowed_mime={"image/jpeg", "application/pdf"},
        max_file_mb=10,
    )

    accepted = validate_attachment(candidate, policy)

    assert accepted.mime == "application/pdf"
    assert accepted.safe_name == "report.pdf"


def test_unsupported_mime_is_rejected() -> None:
    candidate = AttachmentCandidate(
        source=AttachmentSource.DOC,
        original_name="macro.docm",
        content_type="application/vnd.ms-word.document.macroEnabled.12",
        size_bytes=1024,
    )
    policy = AttachmentPolicy(allowed_mime={"image/jpeg"}, max_file_mb=10)

    try:
        validate_attachment(candidate, policy)
    except AttachmentRejection as exc:
        assert exc.reason == "unsupported_mime"
    else:
        raise AssertionError("expected AttachmentRejection")


def test_oversized_attachment_is_rejected() -> None:
    candidate = AttachmentCandidate(
        source=AttachmentSource.PHOTO,
        original_name="big.jpg",
        content_type="image/jpeg",
        size_bytes=11 * 1024 * 1024,
    )
    policy = AttachmentPolicy(allowed_mime={"image/jpeg"}, max_file_mb=10)

    try:
        validate_attachment(candidate, policy)
    except AttachmentRejection as exc:
        assert exc.reason == "size_limit"
    else:
        raise AssertionError("expected AttachmentRejection")
