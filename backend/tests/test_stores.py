"""Unit tests for call intelligence database stores (job_models.py)."""

import uuid

import pytest

import state


class TestSpeakerStore:
    """Tests for SpeakerStore CRUD operations."""

    def _make_speaker(self, name="Test Speaker"):
        sid = str(uuid.uuid4())
        result = state.speaker_store.create(sid, name, f"speakers/{name}")
        return sid, result

    def test_create_and_get(self):
        sid, result = self._make_speaker("CreateGet")
        try:
            assert result["speaker_id"] == sid
            assert result["name"] == "CreateGet"

            fetched = state.speaker_store.get(sid)
            assert fetched is not None
            assert fetched["name"] == "CreateGet"
        finally:
            state.speaker_store.delete(sid)

    def test_get_by_name(self):
        sid, _ = self._make_speaker("ByName")
        try:
            found = state.speaker_store.get_by_name("ByName")
            assert found is not None
            assert found["speaker_id"] == sid
        finally:
            state.speaker_store.delete(sid)

    def test_get_by_name_not_found(self):
        result = state.speaker_store.get_by_name("NonexistentSpeaker12345")
        assert result is None

    def test_list_all(self):
        sid, _ = self._make_speaker("ListAll")
        try:
            speakers = state.speaker_store.list_all()
            names = [s["name"] for s in speakers]
            assert "ListAll" in names
        finally:
            state.speaker_store.delete(sid)

    def test_update(self):
        sid, _ = self._make_speaker("BeforeUpdate")
        try:
            state.speaker_store.update(sid, name="AfterUpdate")
            fetched = state.speaker_store.get(sid)
            assert fetched["name"] == "AfterUpdate"
        finally:
            state.speaker_store.delete(sid)

    def test_delete(self):
        sid, _ = self._make_speaker("ToDelete")
        state.speaker_store.delete(sid)
        assert state.speaker_store.get(sid) is None

    def test_increment_call_count(self):
        sid, _ = self._make_speaker("CallCount")
        try:
            state.speaker_store.increment_call_count(sid, 120.5)
            fetched = state.speaker_store.get(sid)
            assert fetched["call_count"] == 1
            assert fetched["total_speaking_time_seconds"] == 120.5

            state.speaker_store.increment_call_count(sid, 30.0)
            fetched2 = state.speaker_store.get(sid)
            assert fetched2["call_count"] == 2
            assert fetched2["total_speaking_time_seconds"] == 150.5
        finally:
            state.speaker_store.delete(sid)


class TestCallMetadataStore:
    """Tests for CallMetadataStore operations."""

    def _make_call(self, job_id=None, **kwargs):
        jid = job_id or str(uuid.uuid4())
        # Insert a dummy job first using a single connection
        from job_models import TranscriptionJob
        job = TranscriptionJob(jid)
        job.status = "completed"
        job.progress = 100
        job.progress_message = "Done"
        job.language = "en"
        # Use try/except since job may already exist
        try:
            state.job_store.create(job)
        except Exception:
            pass
        result = state.call_metadata_store.create(jid, **kwargs)
        return jid, result

    def test_create_and_get(self):
        jid, result = self._make_call(source_type="test", title="Test Call")
        try:
            assert result["job_id"] == jid
            fetched = state.call_metadata_store.get(jid)
            assert fetched is not None
            assert fetched["title"] == "Test Call"
        finally:
            state.call_metadata_store.delete(jid)
            state.job_store.delete(jid)

    def test_get_not_found(self):
        assert state.call_metadata_store.get("nonexistent-12345") is None

    def test_update(self):
        jid, _ = self._make_call()
        try:
            state.call_metadata_store.update(jid, title="Updated Title", context_path="test/path", context_assigned=1)
            fetched = state.call_metadata_store.get(jid)
            assert fetched["title"] == "Updated Title"
            assert fetched["context_path"] == "test/path"
            assert fetched["context_assigned"] == 1
        finally:
            state.call_metadata_store.delete(jid)
            state.job_store.delete(jid)

    def test_list_recent(self):
        jid, _ = self._make_call(title="Recent Test")
        try:
            calls = state.call_metadata_store.list_recent(limit=10)
            ids = [c["job_id"] for c in calls]
            assert jid in ids
        finally:
            state.call_metadata_store.delete(jid)
            state.job_store.delete(jid)

    def test_count(self):
        jid, _ = self._make_call()
        try:
            count = state.call_metadata_store.count()
            assert count >= 1
        finally:
            state.call_metadata_store.delete(jid)
            state.job_store.delete(jid)


class TestCallSpeakerStore:
    """Tests for CallSpeakerStore operations."""

    def test_add_and_get_for_call(self):
        call_id = str(uuid.uuid4())
        speaker_id = str(uuid.uuid4())
        state.speaker_store.create(speaker_id, f"SP_{speaker_id[:8]}", f"speakers/SP_{speaker_id[:8]}")
        try:
            state.call_speaker_store.add(
                call_id=call_id,
                speaker_id=speaker_id,
                speaker_label="SPEAKER_00",
                confidence=0.85,
            )
            speakers = state.call_speaker_store.get_for_call(call_id)
            assert len(speakers) == 1
            assert speakers[0]["speaker_id"] == speaker_id
            assert speakers[0]["confidence"] == 0.85
        finally:
            state.call_speaker_store.delete_for_call(call_id)
            state.speaker_store.delete(speaker_id)

    def test_confirm(self):
        call_id = str(uuid.uuid4())
        speaker_id = str(uuid.uuid4())
        state.speaker_store.create(speaker_id, f"CF_{speaker_id[:8]}", f"speakers/CF_{speaker_id[:8]}")
        try:
            state.call_speaker_store.add(call_id=call_id, speaker_id=speaker_id)
            assert state.call_speaker_store.all_confirmed(call_id) is False

            state.call_speaker_store.confirm(call_id, speaker_id)
            assert state.call_speaker_store.all_confirmed(call_id) is True
        finally:
            state.call_speaker_store.delete_for_call(call_id)
            state.speaker_store.delete(speaker_id)

    def test_all_confirmed_multiple(self):
        call_id = str(uuid.uuid4())
        s1 = str(uuid.uuid4())
        s2 = str(uuid.uuid4())
        state.speaker_store.create(s1, f"M1_{s1[:8]}", f"speakers/M1_{s1[:8]}")
        state.speaker_store.create(s2, f"M2_{s2[:8]}", f"speakers/M2_{s2[:8]}")
        try:
            state.call_speaker_store.add(call_id=call_id, speaker_id=s1)
            state.call_speaker_store.add(call_id=call_id, speaker_id=s2)

            # Only one confirmed
            state.call_speaker_store.confirm(call_id, s1)
            assert state.call_speaker_store.all_confirmed(call_id) is False

            # Both confirmed
            state.call_speaker_store.confirm(call_id, s2)
            assert state.call_speaker_store.all_confirmed(call_id) is True
        finally:
            state.call_speaker_store.delete_for_call(call_id)
            state.speaker_store.delete(s1)
            state.speaker_store.delete(s2)

    def test_delete_for_call(self):
        call_id = str(uuid.uuid4())
        speaker_id = str(uuid.uuid4())
        state.speaker_store.create(speaker_id, f"DL_{speaker_id[:8]}", f"speakers/DL_{speaker_id[:8]}")
        try:
            state.call_speaker_store.add(call_id=call_id, speaker_id=speaker_id)
            assert len(state.call_speaker_store.get_for_call(call_id)) == 1

            state.call_speaker_store.delete_for_call(call_id)
            assert len(state.call_speaker_store.get_for_call(call_id)) == 0
        finally:
            state.speaker_store.delete(speaker_id)
