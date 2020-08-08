import os
import unittest

import torch

from nagisa.dl.torch.misc.test import TorchTestCase
from nagisa.core.misc.io import download_url_to_file, prepare_resource
from nagisa.dl.torch.misc.io import load_state_dict

skip_if_local = unittest.skipIf(os.getenv("LOCAL") is not None, "local testing")

skip_if_local_and_no_proxy = unittest.skipIf(
    "proxychains" not in os.environ.get("LD_PRELOAD", "") and os.getenv("LOCAL") is not None,
    "local testing and no proxy",
)


class TestDownloadUrlToFile(TorchTestCase):

    dest = "/tmp/nagisa.io.file__DOWNLOADED__"

    def tearDown(self):
        if os.path.exists(self.dest):
            os.remove(self.dest)

    @skip_if_local_and_no_proxy
    def test_small_file(self):
        download_url_to_file(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            self.dest,
            hash_prefix="cf7562b422f97f6b3d6dbfd9394df928735422becd8ab2d8d1c9902f2c15a077",
        )

        data = torch.load(self.dest)
        self.assertEqual(data["tensor"], torch.tensor(range(100), dtype=float))
        self.assertEqual(data["string"], "hello world")

    @skip_if_local
    def test_big_file(self):
        # A ~40MB zip file which requires confirm code
        download_url_to_file(
            "https://drive.google.com/file/d/1X0NTkVNlXBvC0uRj1vWl4Ow7MA4bNQtk/view",
            self.dest,
            hash_prefix="71c70feee092db533f959362f866896afa59a57fb04c290f16667a37882589d3",
        )


class TestLoadStateDict(TorchTestCase):
    def tearDown(self):
        os.remove(self.dest)

    def test_load_local_small_file(self):
        os.makedirs("/tmp/a/", exist_ok=True)
        data = {
            "tensor": torch.tensor(range(100), dtype=float),
            "string": "hello world",
        }
        torch.save(
            data, "/tmp/a/test.pth",
            **(
                {
                    '_use_new_zipfile_serialization': False
                } if torch.__version__.startswith('1.6.') else {}
            )
        )
        data, self.dest = load_state_dict(
            "/tmp/a/test.pth",
            model_dir="/tmp/a/",
            return_filename=True,
        )

        self.assertEqual(data["tensor"], torch.tensor(range(100), dtype=float))
        self.assertEqual(data["string"], "hello world")

    @skip_if_local_and_no_proxy
    def test_small_file(self):
        data, self.dest = load_state_dict(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            return_filename=True,
        )

        self.assertEqual(data["tensor"], torch.tensor(range(100), dtype=float))
        self.assertEqual(data["string"], "hello world")

    @skip_if_local_and_no_proxy
    def test_small_file_to_custom_dir(self):
        os.makedirs("/tmp/a/", exist_ok=True)
        data, self.dest = load_state_dict(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            model_dir="/tmp/a/",
            return_filename=True,
        )

        self.assertEqual(data["tensor"], torch.tensor(range(100), dtype=float))
        self.assertEqual(data["string"], "hello world")

    @skip_if_local
    def test_big_file(self):
        # A ~40MB zip file which requires confirm code
        os.makedirs("/tmp/a/", exist_ok=True)
        self.dest = prepare_resource(
            "https://drive.google.com/file/d/1X0NTkVNlXBvC0uRj1vWl4Ow7MA4bNQtk/view",
            "/tmp/a/",
            check_hash="71c70feee092db533f959362f866896afa59a57fb04c290f16667a37882589d3",
        )
