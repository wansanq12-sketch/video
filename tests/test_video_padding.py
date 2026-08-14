import contextlib
import importlib
import io
import unittest

import numpy as np


def load_video_padding(test_case):
    try:
        return importlib.import_module("video_padding")
    except ModuleNotFoundError as exc:
        test_case.fail(f"video_padding module is not implemented: {exc}")


class VideoPaddingTests(unittest.TestCase):
    def test_supported_formats_are_only_h264_and_h265_mp4(self):
        video_padding = load_video_padding(self)

        self.assertEqual(
            video_padding.MP4_VIDEO_FORMATS,
            {
                "video/h264-mp4",
                "video/h265-mp4",
            },
        )

    def test_even_mp4_frames_are_unchanged_without_logging(self):
        video_padding = load_video_padding(self)
        frames = [
            np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3),
            np.full((4, 6, 3), 127, dtype=np.uint8),
        ]
        originals = [frame.copy() for frame in frames]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = video_padding.pad_mp4_frames(
                frames, "video/h265-mp4"
            )

        self.assertIs(result, frames)
        self.assertEqual(output.getvalue(), "")
        for result_frame, original in zip(result, originals):
            np.testing.assert_array_equal(result_frame, original)

    def test_odd_width_is_edge_padded_for_h264_and_h265(self):
        video_padding = load_video_padding(self)
        original = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)

        for output_format in video_padding.MP4_VIDEO_FORMATS:
            with self.subTest(output_format=output_format):
                frames = [original.copy(), original.copy()]
                output = io.StringIO()

                with contextlib.redirect_stdout(output):
                    result = video_padding.pad_mp4_frames(
                        frames, output_format
                    )

                self.assertIs(result, frames)
                self.assertEqual(result[0].shape, (4, 6, 3))
                self.assertEqual(result[0].dtype, original.dtype)
                self.assertEqual(len(result), 2)
                np.testing.assert_array_equal(result[0][:, :5], original)
                np.testing.assert_array_equal(
                    result[0][:, 5], original[:, 4]
                )
                self.assertEqual(
                    output.getvalue(),
                    "### VideoCrypt: Padded video frames from "
                    "5x4 to 6x4 for codec compatibility.\n",
                )

    def test_odd_height_is_edge_padded_on_the_bottom(self):
        video_padding = load_video_padding(self)
        original = np.arange(5 * 4 * 3, dtype=np.uint8).reshape(5, 4, 3)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = video_padding.pad_mp4_frames(
                [original.copy()], "video/h264-mp4"
            )

        self.assertEqual(result[0].shape, (6, 4, 3))
        np.testing.assert_array_equal(result[0][:5], original)
        np.testing.assert_array_equal(result[0][5], original[4])
        self.assertEqual(
            output.getvalue(),
            "### VideoCrypt: Padded video frames from "
            "4x5 to 4x6 for codec compatibility.\n",
        )

    def test_odd_width_and_height_copy_right_bottom_and_corner_edges(self):
        video_padding = load_video_padding(self)
        original = np.arange(3 * 5 * 4, dtype=np.uint8).reshape(3, 5, 4)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = video_padding.pad_mp4_frames(
                [original.copy()], "video/h265-mp4"
            )

        self.assertEqual(result[0].shape, (4, 6, 4))
        self.assertEqual(result[0].dtype, original.dtype)
        np.testing.assert_array_equal(result[0][:3, :5], original)
        np.testing.assert_array_equal(result[0][:3, 5], original[:, 4])
        np.testing.assert_array_equal(result[0][3, :5], original[2])
        np.testing.assert_array_equal(result[0][3, 5], original[2, 4])
        self.assertEqual(
            output.getvalue(),
            "### VideoCrypt: Padded video frames from "
            "5x3 to 6x4 for codec compatibility.\n",
        )

    def test_gif_and_webp_keep_odd_dimensions(self):
        video_padding = load_video_padding(self)
        original = np.arange(3 * 5 * 3, dtype=np.uint8).reshape(3, 5, 3)

        for output_format in ("image/gif", "image/webp"):
            with self.subTest(output_format=output_format):
                frames = [original.copy()]
                output = io.StringIO()

                with contextlib.redirect_stdout(output):
                    result = video_padding.pad_mp4_frames(
                        frames, output_format
                    )

                self.assertIs(result, frames)
                self.assertEqual(result[0].shape, original.shape)
                self.assertEqual(output.getvalue(), "")
                np.testing.assert_array_equal(result[0], original)


if __name__ == "__main__":
    unittest.main()
