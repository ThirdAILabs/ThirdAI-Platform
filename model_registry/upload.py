import base64
import hashlib
from urllib.parse import urljoin

import requests
import tqdm


class RegistryClient:
    def __init__(self, url: str, apikey: str):
        self.url = url
        self.apikey = apikey

    def upload_model(
        self,
        path: str,
        name: str,
        model_type: str,
        model_subtype: str,
        description: str = "",
    ):
        with open(path, "rb") as file:
            size = 0
            checksum = hashlib.sha256()
            while chunk := file.read(1024 * 1024):
                checksum.update(chunk)
                size += len(chunk)

        res = requests.post(
            urljoin(self.url, "/api/v1/upload-start"),
            json={
                "model_name": name,
                "model_type": model_type,
                "model_subtype": model_subtype,
                "access": "public",
                "size": size,
                "checksum": base64.encodebytes(checksum.digest()).decode().strip(),
                "description": description,
            },
            headers={"Authorization": f"Bearer {self.apikey}"},
        )
        if res.status_code != 200:
            raise ValueError(
                f"upload start failed {res.status_code} {str(res.content)}"
            )

        session_token = res.json()["session_token"]

        with open(path, "rb") as file:
            offset = 0
            with tqdm.tqdm(total=size) as bar:
                while chunk := file.read(1024 * 1024):
                    res = requests.post(
                        urljoin(self.url, "/api/v1/upload-chunk"),
                        headers={
                            "Authorization": f"Bearer {session_token}",
                            "Content-Range": f"bytes {offset}-{offset + len(chunk)}/{size}",
                        },
                        data=chunk,
                    )
                    if res.status_code != 200:
                        raise ValueError(
                            f"upload chunk failed {res.status_code} {str(res.content)}"
                        )

                    offset += len(chunk)
                    bar.update(len(chunk))

        res = requests.post(
            urljoin(self.url, "/api/v1/upload-commit"),
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if res.status_code != 200:
            raise ValueError(
                f"upload commit failed {res.status_code} {str(res.content)}"
            )

    def delete_model(self, name: str):
        res = requests.post(
            urljoin(self.url, "/api/v1/delete-model"),
            params={"model_name": name},
            headers={"Authorization": f"Bearer {self.apikey}"},
        )
        if res.status_code != 200:
            raise ValueError(
                f"delete model failed {res.status_code} {str(res.content)}"
            )


def main():
    client = RegistryClient(
        url="https://model-registry.thirdai-aws.com",
        apikey="<API KEY HERE>",
    )

    client.upload_model(
        "<PATH TO MODEL>",
        name="<MODEL NAME>",
        model_type="<MODEL TYPE>",
        model_subtype="<MODEL SUBTYPE>",
        description="<MODEL DESCRIPTION>",
    )


if __name__ == "__main__":
    main()
