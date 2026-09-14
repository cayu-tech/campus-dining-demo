"""Administrative request identities cannot become arbitrary filesystem paths."""

import pytest
from fastapi import HTTPException

from operations.demo_reset import request_identity


def test_request_identity_canonicalizes_uuid():
    assert request_identity("{A3D2BBD4-BCA4-4AA0-B7BB-195CF74E2158}") == (
        "a3d2bbd4-bca4-4aa0-b7bb-195cf74e2158"
    )


@pytest.mark.parametrize("value", ["../../outside", "", "request", None, True])
def test_request_identity_rejects_non_uuid(value):
    with pytest.raises(HTTPException) as rejected:
        request_identity(value)
    assert rejected.value.status_code == 422
