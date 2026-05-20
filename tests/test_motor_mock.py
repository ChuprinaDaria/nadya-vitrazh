from vitrazh.models import InstallationState
from vitrazh.motor.mock import MockMotorController


def test_mock_motor_initial_state():
    m = MockMotorController()
    assert m.get_state() == InstallationState.ROTATING


def test_mock_motor_state_change():
    m = MockMotorController()
    m.set_state(InstallationState.ASSEMBLED)
    assert m.get_state() == InstallationState.ASSEMBLED
    m.shutdown()
