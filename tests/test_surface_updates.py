import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'boayo'))
from boayo_surface_updates import SurfacePublisher
from boayo_app_window import BoayoAppFrame


class SurfaceUpdatesTests(unittest.TestCase):
    def test_cached_chrome_matches_complete_render_across_focus_changes(self):
        frame = BoayoAppFrame(640,440,'Cached frame')
        def paint(canvas,rect):
            canvas.rect(rect.x,rect.y,rect.width,rect.height,(32,64,96))
            canvas.text('TEST',rect.x+10,rect.y+10,(224,224,224))
        for focused,hovered in [(False,None),(True,'move'),(True,'resize_right')]:
            frame.focused,frame.hovered = focused,hovered
            expected = frame._render_uncached(paint).copy()
            np.testing.assert_array_equal(frame.render(paint), expected)
        original = frame._render_uncached
        frame._render_uncached = Mock(wraps=original)
        frame.render(paint)
        frame._render_uncached.assert_not_called()

    def test_small_edit_sends_only_pixels_and_identical_frame_sends_nothing(self):
        wm = Mock()
        publisher = SurfacePublisher(wm, 7)
        image = np.zeros((440,640,3), dtype=np.uint8)
        publisher.publish(image)
        image[100:108,200:208] = (32,128,224)
        publisher.publish(image)
        self.assertEqual(publisher.last_rect, (200,100,8,8))
        self.assertEqual(publisher.last_bytes, 192)
        self.assertEqual(wm.update_surface.call_args.kwargs, dict(x=200,y=100))
        self.assertFalse(publisher.publish(image.copy()))
        self.assertEqual(wm.update_surface.call_count, 2)

    def test_failed_upload_is_retried_without_losing_dirty_pixels(self):
        wm = Mock()
        publisher = SurfacePublisher(wm, 1)
        image = np.zeros((12,16,3), dtype=np.uint8)
        publisher.publish(image)
        image[-1,-1] = 255
        wm.update_surface.side_effect = RuntimeError('IPC failure')
        with self.assertRaises(RuntimeError): publisher.publish(image)
        self.assertEqual(publisher.previous[-1,-1].tolist(), [0,0,0])
        wm.update_surface.side_effect = None
        self.assertTrue(publisher.publish(image))
        self.assertEqual(publisher.last_rect, (15,11,1,1))

    def test_snapshot_does_not_alias_the_application_canvas(self):
        wm = Mock()
        publisher = SurfacePublisher(wm, 1)
        image = np.zeros((10,20,3), dtype=np.uint8)
        publisher.publish(image)
        image[0,0] = 255
        image[-1,-1] = 128
        self.assertTrue(publisher.publish(image))
        self.assertEqual(publisher.last_rect, (0,0,20,10))


if __name__ == '__main__': unittest.main()
