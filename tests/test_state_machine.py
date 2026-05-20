from vitrazh.models import InstallationState, PoseClass, StateMachineConfig
from vitrazh.state_machine import VitrazStateMachine


def test_initial_state_is_rotating():
    sm = VitrazStateMachine()
    assert sm.state == InstallationState.ROTATING


def test_person_presence_triggers_assembly():
    cfg = StateMachineConfig(presence_delay=1.0)
    sm = VitrazStateMachine(cfg)

    # Person appears at t=0
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.ROTATING

    # Not enough time yet
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.5)
    assert sm.state == InstallationState.ROTATING

    # Enough time — should assemble
    sm.update(person_present=True, pose=PoseClass.IDLE, now=1.0)
    assert sm.state == InstallationState.ASSEMBLING

    # Next tick — assembled
    sm.update(person_present=True, pose=PoseClass.IDLE, now=1.1)
    assert sm.state == InstallationState.ASSEMBLED


def test_person_leaves_triggers_rotation():
    cfg = StateMachineConfig(presence_delay=0.0, absence_delay=2.0)
    sm = VitrazStateMachine(cfg)

    # Person present — assemble immediately
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.1)  # assembling -> assembled

    # Person leaves
    sm.update(person_present=False, pose=PoseClass.IDLE, now=1.0)
    assert sm.state == InstallationState.ASSEMBLED  # not yet

    sm.update(person_present=False, pose=PoseClass.IDLE, now=3.1)
    assert sm.state == InstallationState.ROTATING


def test_photo_pose_triggers_rotation():
    cfg = StateMachineConfig(presence_delay=0.0, photo_resume_delay=1.0)
    sm = VitrazStateMachine(cfg)

    # Assemble
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.1)
    assert sm.state == InstallationState.ASSEMBLED

    # Person starts photographing
    sm.update(person_present=True, pose=PoseClass.PHOTOGRAPHING, now=1.0)
    assert sm.state == InstallationState.ASSEMBLED  # not yet

    # After delay — disassemble
    sm.update(person_present=True, pose=PoseClass.PHOTOGRAPHING, now=2.1)
    assert sm.state == InstallationState.DISASSEMBLING

    # Next tick — rotating
    sm.update(person_present=True, pose=PoseClass.IDLE, now=2.2)
    assert sm.state == InstallationState.ROTATING


def test_phone_viewing_also_triggers_rotation():
    cfg = StateMachineConfig(presence_delay=0.0, photo_resume_delay=0.5)
    sm = VitrazStateMachine(cfg)

    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_present=True, pose=PoseClass.IDLE, now=0.1)

    sm.update(person_present=True, pose=PoseClass.PHONE_VIEWING, now=1.0)
    sm.update(person_present=True, pose=PoseClass.PHONE_VIEWING, now=1.6)
    assert sm.state == InstallationState.DISASSEMBLING
