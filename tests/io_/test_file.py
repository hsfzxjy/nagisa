import os
import unittest

import torch

from nagisa.io.file import download_url_to_file
from nagisa.misc.test import TorchTestCase


class TestDownloadUrlToFile(TorchTestCase):

    dest = "/tmp/nagisa.io.file__DOWNLOADED__"

    def tearDown(self):
        if os.path.exists(self.dest):
            os.remove(self.dest)

    def test_small_file(self):
        download_url_to_file(
            "https://drive.google.com/file/d/1XWYEAjrcJQ7VQbxJtEk37v5q5Otnm3dV/view",
            self.dest,
            hash_prefix="cf7562b422f97f6b3d6dbfd9394df928735422becd8ab2d8d1c9902f2c15a077",
        )

        data = torch.load(self.dest)
        self.assertTensorEqual(data["tensor"], torch.tensor(range(100), dtype=float))
        self.assertEqual(data["string"], "hello world")

    @unittest.skipIf(os.getenv("LOCAL") is not None, "ENVVAR `LOCAL` set")
    def test_big_file(self):
        # A ~40MB zip file which requires confirm code
        download_url_to_file(
            "https://drive.google.com/file/d/1X0NTkVNlXBvC0uRj1vWl4Ow7MA4bNQtk/view",
            self.dest,
            hash_prefix="71c70feee092db533f959362f866896afa59a57fb04c290f16667a37882589d3",
        )

