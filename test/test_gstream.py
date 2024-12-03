from degirum_tools.video_support import open_video_stream


def test_opencv_video_source():
    # Test with a sample video file (ensure the file exists for the test)
    video_file = "sample.mp4"  # Replace with an actual file path
    with open_video_stream(video_file) as stream:
        assert stream.isOpened(), "Failed to open video file"
        ret, frame = stream.read()
        assert ret, "Failed to read a frame"
        assert frame is not None, "Frame is None"


def test_gstreamer_pipeline():
    # Test with a sample GStreamer pipeline
    gst_pipeline = "filesrc location=Traffic.mp4 ! decodebin ! videoconvert ! video/x-raw,format=RGB ! appsink name=sink"
    try:
        with open_video_stream(gst_pipeline) as stream:
            assert stream.isOpened(), "Failed to open GStreamer pipeline"
            ret, frame = stream.read()
            assert ret, "Failed to read a frame from GStreamer pipeline"
            assert frame is not None, "Frame is None from GStreamer pipeline"
    except ImportError:
        print("GStreamer not available, skipping test")


def test_invalid_gstreamer_pipeline():
    invalid_pipeline = "invalid_pipeline ! appsink"
    try:
        with open_video_stream(invalid_pipeline):
            pass  # This should not execute if the pipeline is invalid
    except Exception as e:
        # Match specific error messages
        assert "Invalid GStreamer pipeline" in str(e) or "failed to start" in str(e), (
            f"Unexpected error message: {e}"
        )
    else:
        assert False, "Did not raise error for invalid GStreamer pipeline"


def test_youtube_url():
    # Replace with a valid YouTube URL for testing
    youtube_url = "https://youtu.be/dQw4w9WgXcQ"
    try:
        with open_video_stream(youtube_url) as stream:
            assert stream.isOpened(), "Failed to open YouTube URL"
    except Exception as e:
        print(f"Error with YouTube test: {e}")


if __name__ == "__main__":
    print("Running tests...")
    test_opencv_video_source()
    test_gstreamer_pipeline()
    test_invalid_gstreamer_pipeline()
    test_youtube_url()
    print("All tests completed.")
