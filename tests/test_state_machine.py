from vitrazh.models import InstallationState, PoseClass, StateMachineConfig
from vitrazh.state_machine import VitrazStateMachine


def test_initial_state_is_spinning():
    sm = VitrazStateMachine()
    assert sm.state == InstallationState.SPINNING


def test_one_person_triggers_teasing():
    sm = VitrazStateMachine()
    sm.update(person_count=1, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.TEASING


def test_one_person_never_assembles():
    """Core concept: painting cannot assemble for one person."""
    sm = VitrazStateMachine()
    # Even after a long time, one person stays in teasing
    sm.update(person_count=1, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_count=1, pose=PoseClass.IDLE, now=60.0)
    sm.update(person_count=1, pose=PoseClass.IDLE, now=120.0)
    assert sm.state == InstallationState.TEASING


def test_two_people_start_pursuit():
    sm = VitrazStateMachine()
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.PURSUIT


def test_pursuit_assembles_after_duration():
    cfg = StateMachineConfig(pursuit_duration=5.0)
    sm = VitrazStateMachine(cfg)

    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.PURSUIT

    # Not enough time
    sm.update(person_count=2, pose=PoseClass.IDLE, now=3.0)
    assert sm.state == InstallationState.PURSUIT

    # After pursuit_duration → assembling
    sm.update(person_count=2, pose=PoseClass.IDLE, now=5.0)
    assert sm.state == InstallationState.ASSEMBLING

    # Next tick → assembled
    sm.update(person_count=2, pose=PoseClass.IDLE, now=5.1)
    assert sm.state == InstallationState.ASSEMBLED


def test_friend_leaves_breaks_painting():
    """If one person leaves while assembled, painting breaks (teasing)."""
    cfg = StateMachineConfig(pursuit_duration=0.0)
    sm = VitrazStateMachine(cfg)

    # Assemble with 2 people
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.1)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.2)
    assert sm.state == InstallationState.ASSEMBLED

    # One person leaves → teasing
    sm.update(person_count=1, pose=PoseClass.IDLE, now=1.0)
    assert sm.state == InstallationState.TEASING


def test_everyone_leaves_returns_to_spinning():
    cfg = StateMachineConfig(absence_delay=2.0)
    sm = VitrazStateMachine(cfg)

    sm.update(person_count=1, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.TEASING

    # Everyone leaves
    sm.update(person_count=0, pose=PoseClass.IDLE, now=1.0)
    assert sm.state == InstallationState.TEASING  # grace period

    sm.update(person_count=0, pose=PoseClass.IDLE, now=3.1)
    assert sm.state == InstallationState.SPINNING


def test_photo_pose_restarts_pursuit():
    cfg = StateMachineConfig(pursuit_duration=0.0, photo_resume_delay=1.0)
    sm = VitrazStateMachine(cfg)

    # Assemble
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.1)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.2)
    assert sm.state == InstallationState.ASSEMBLED

    # Photo pose → restarts pursuit
    sm.update(person_count=2, pose=PoseClass.PHOTOGRAPHING, now=1.0)
    sm.update(person_count=2, pose=PoseClass.PHOTOGRAPHING, now=2.1)
    assert sm.state == InstallationState.PURSUIT


def test_pursuit_interrupted_by_person_leaving():
    """If 2→1 during pursuit, switch to teasing."""
    sm = VitrazStateMachine()

    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    assert sm.state == InstallationState.PURSUIT

    sm.update(person_count=1, pose=PoseClass.IDLE, now=5.0)
    assert sm.state == InstallationState.TEASING


def test_assembled_everyone_leaves_returns_to_spinning():
    """ASSEMBLED → 0 people → SPINNING (not teasing)."""
    cfg = StateMachineConfig(pursuit_duration=0.0, absence_delay=1.0)
    sm = VitrazStateMachine(cfg)

    # Assemble
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.0)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.1)
    sm.update(person_count=2, pose=PoseClass.IDLE, now=0.2)
    assert sm.state == InstallationState.ASSEMBLED

    # Everyone leaves → after grace period → spinning
    sm.update(person_count=0, pose=PoseClass.IDLE, now=1.0)
    sm.update(person_count=0, pose=PoseClass.IDLE, now=2.5)
    assert sm.state == InstallationState.SPINNING
