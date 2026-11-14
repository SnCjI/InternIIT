"""Example: multispectral snake-by-row scan driven from the PC (the PC is the master).

The stage and camera classes are placeholders for the supervisor's own code (stage base code and
PCO SDK). The laser driver is used in MODE TRIG: at every position the board waits for the stage
"in position" edge on its BNC input, then runs one hardware-timed frame per laser.
"""
from dpss_client import DPSSDriver


def snake_positions(n_rows, n_cols, pitch_x_mm, pitch_y_mm, x0=0.0, y0=0.0):
    """Row by row; odd rows run backwards so the stage never makes a long return move."""
    for r in range(n_rows):
        cols = range(n_cols) if r % 2 == 0 else range(n_cols - 1, -1, -1)
        for c in cols:
            yield r, c, x0 + c * pitch_x_mm, y0 + r * pitch_y_mm


class StagePlaceholder:
    """Replace with the supervisor's HO-MPC-4H base code."""
    def move_to(self, x_mm, y_mm):
        raise NotImplementedError


class CameraPlaceholder:
    """Replace with the PCO SDK calls (pco.python). Mode A: the PC triggers each exposure."""
    def arm_for(self, n_images, exposure_us, external_trigger):
        raise NotImplementedError

    def wait_images(self, n):
        raise NotImplementedError


def run_scan(drv, stage, camera, plan, lasers=(1, 2, 3, 4), currents_ma=None,
             settle_us=2000, lead_us=5000, exposure_us=10_000, board_triggers_camera=False):
    currents_ma = currents_ma or {1: 300.0, 2: 300.0, 3: 300.0, 4: 300.0}
    drv.reset()                                   # operator closed key + interlock
    for ch in lasers:
        drv.set_current(ch, currents_ma[ch])
    drv.arm()
    drv.mode('TRIG')
    drv.settle(settle_us); drv.lead(lead_us)
    if board_triggers_camera:                     # mode B (needs JP501 closed and the camera
        drv.camera_trigger(True)                  # in external trigger mode)
    camera.arm_for(len(lasers), exposure_us, external_trigger=board_triggers_camera)
    images = []
    for r, c, x, y in plan:
        drv.position(lasers, wait=True)           # queue the frames before the move
        stage.move_to(x, y)                       # stage raises its BNC trigger on arrival
        drv.wait_frames(len(lasers))
        images.append(((r, c), camera.wait_images(len(lasers))))
    drv.disarm()
    return images


if __name__ == '__main__':
    drv = DPSSDriver.open('COM5')
    print(drv.idn())
    plan = list(snake_positions(3, 4, 0.5, 0.5))
    print([(r, c) for r, c, _, _ in plan])
