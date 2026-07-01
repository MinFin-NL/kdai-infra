# QES/app/core/question_extraction.py
import logging
import requests
from app.config import CONFIG
from app.services.minio_service import MinioService
from app.services.segment_tracker import SegmentTracker
from app.services.error_service import NotificationException

LOGGER = logging.getLogger(__name__)

class QuestionExtraction:
    def __init__(self):
        self.minio_service = MinioService()
        self.segment_tracker = SegmentTracker()

    def extract_questions(self, debate_id: str, current_segment_id: str) -> list[str]:
        """Extract questions from the given text using the specified model."""
        previous_segment_id = self.segment_tracker.get_previous_segment(debate_id, current_segment_id)
        previous_segment_transcript = ""

        if previous_segment_id:
            LOGGER.info(f"Previous segment found: {previous_segment_id}")
            transcript_path = f"{debate_id}/transcripts/{previous_segment_id}/corrected_transcript.txt"
            if self.minio_service.does_file_exists(transcript_path):
                previous_segment_transcript = self._get_segment_text(debate_id, previous_segment_id)
                if not previous_segment_transcript:
                    LOGGER.warning(f"Transcript for segment {previous_segment_id} is empty.")
            else:
                LOGGER.warning(f"Transcript for segment {previous_segment_id} does not exist.")
        else:
            LOGGER.warning(f"No previous segment found for {current_segment_id}.")

        current_segment_transcript = self._get_segment_text(debate_id, current_segment_id)
        if not current_segment_transcript:
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction.extract_questions",
                error_code="TRANSCRIPT_EMPTY",
                error_message=f"Transcript for segment {current_segment_id} is empty."
            )

        LOGGER.info(f"Sending data to LLM for segment {current_segment_id}...")
        llm_response = self._send_data_to_llm(debate_id, previous_segment_transcript, current_segment_transcript)
        questions = self._parse_response(debate_id, llm_response)
        if not questions:
            LOGGER.warning(f"No questions found in segment {current_segment_id}.")
            return []

        LOGGER.info(f"Questions extracted: {questions}")
        self._notify_backend(debate_id, questions, current_segment_id, previous_segment_id)

    def _get_segment_text(self, debate_id: str, current_segment_id: str) -> str:
        """Retrieve the text of the segment from Minio."""
        try:
            object_name = f"{debate_id}/transcripts/{current_segment_id}/corrected_transcript.txt"
            return self.minio_service.download_file(debate_id, object_name)
        except Exception as e:
            LOGGER.error(f"Error retrieving segment text: {e}")
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction._get_segment_text",
                error_code="SEGMENT_RETRIEVAL_ERROR",
                error_message=f"Failed to retrieve segment text for {current_segment_id}: {str(e)}"
            )

    def _send_data_to_llm(self, debate_id: str, previous_segment_transcript: str, current_segment_transcript: str) -> str:
        """Send data to Azure OpenAI (chat completions) and return the text response.

        PIPELINE OVERRIDE: replaces the Ollama `/generate` call with Azure OpenAI's REST API,
        so the questions feature runs on the managed Azure LLM instead of a local GPU/Ollama.
        The prompt and the downstream `- `-prefixed line parsing are unchanged.
        """
        try:
            endpoint = CONFIG["AZURE_OPENAI_ENDPOINT"].rstrip("/")
            url = (
                f"{endpoint}/openai/deployments/{CONFIG['AZURE_OPENAI_DEPLOYMENT']}"
                f"/chat/completions?api-version={CONFIG['AZURE_OPENAI_API_VERSION']}"
            )

            prompt = f"""
                ### Rol
                Je bent een taalmodel dat parlementaire debattranscripties analyseert en vragen identificeert.

                ### Context
                Je krijgt twee opeenvolgende segmenten uit hetzelfde debat:

                **Segment 1 (context):**
                {previous_segment_transcript}

                **Segment 2 (analyseer dit segment):**
                {current_segment_transcript}

                ### Instructie
                Identificeer in **alleen Segment 2** alle zinnen die een **vraag** vormen. Dit zijn zinnen waarin een spreker:
                - expliciet iets vraagt aan een ander persoon;
                - of een verzoek of instructie geeft die impliciet als vraag bedoeld is (bijv. "Vertel", "Leg uit", "Kunt u aangeven...").

                Let op:
                1. Neem alleen vragen op die **in Segment 2 staan**.
                2. Als een vraag in Segment 1 begint en in Segment 2 eindigt, neem deze **volledig op** (inclusief stuk uit Segment 1), **maar alleen als Segment 2 tekst van de vraag bevat**.
                3. **Behoud de exacte volgorde en formulering** zoals in de transcriptie.
                4. Voeg niets toe, verwijder niets en herschrijf niets.
                5. Als er geen vragen zijn, retourneer een lege lijst.

                ### Output
                Geef een lijst waarin elke vraag op een nieuwe regel staat, met een streepje ervoor:

                - [Vraag 1]
                - [Vraag 2]
                - ...
            """

            response = requests.post(
                url,
                headers={
                    "api-key": CONFIG["AZURE_OPENAI_KEY"],
                    "Content-Type": "application/json",
                },
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 800,
                },
                timeout=60,
            )

            if response.status_code != 200:
                raise NotificationException(
                    debate_id=debate_id,
                    service_name="QES:QuestionExtraction._send_data_to_llm",
                    error_code="LLM_RESPONSE_ERROR",
                    error_message=f"Azure OpenAI returned status code {response.status_code}: {response.text}"
                )

            llm_json = response.json()
            llm_output = (
                llm_json.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not isinstance(llm_output, str) or llm_output == "":
                raise NotificationException(
                    debate_id=debate_id,
                    service_name="QES:QuestionExtraction._send_data_to_llm",
                    error_code="LLM_INVALID_RESPONSE",
                    error_message="Azure OpenAI response did not contain message content"
                )
            return llm_output

        except NotificationException:
            raise
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Request to Azure OpenAI failed: {e}")
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction._send_data_to_llm",
                error_code="LLM_REQUEST_ERROR",
                error_message=str(e)
            )
        except Exception as e:
            LOGGER.error(f"Unexpected error in _send_data_to_llm: {e}")
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction._send_data_to_llm",
                error_code="LLM_CONFIGURATION_ERROR",
                error_message=str(e)
            )

    def _parse_response(self, debate_id: str, response: str) -> list[dict]:
        """Parse the LLM response to extract questions."""
        try:
            LOGGER.info(f"Parsing LLM response")
            # Split the response by new lines and filter out empty lines
            questions = [
                {"text": line[2:].strip()}
                for line in response.split('\n')
                if line.strip().startswith("- ")
            ]
            return questions
        except Exception as e:
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction._parse_response",
                error_code="LLM_PARSING_ERROR",
                error_message=str(e)
            )

    def _notify_backend(self, debate_id: str, questions: list[dict], current_segment_id: str, previous_segment_id: str):
        """Notify the backend with the extracted questions."""
        try:
            LOGGER.info(f"Notifying backend with questions for segment {current_segment_id}...")
            if not questions:
                LOGGER.warning(f"No questions to notify for segment {current_segment_id}.")
                return

            # Prepare the payload for the backend notification
            url = f"{CONFIG['BACKEND_QES_RESULT_URL']}"
            payload = {
                "debateID": debate_id,
                "questions": questions,
                "segment_id": current_segment_id,
                # "previous_segment_id": previous_segment_id,
            }

            LOGGER.info(f"Payload: {payload}")

            headers = {
                "Authorization": f"Bearer {CONFIG['STATIC_API_KEY']}"
            }
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise NotificationException(
                    debate_id=debate_id,
                    service_name="QES:QuestionExtraction._notify_backend",
                    error_code="BACKEND_NOTIFICATION_ERROR",
                    error_message=f"Backend returned status code {response.status_code}, response: {response.text}"
                )
        except Exception as e:
            raise NotificationException(
                debate_id=debate_id,
                service_name="QES:QuestionExtraction._notify_backend",
                error_code="BACKEND_NOTIFICATION_ERROR",
                error_message=str(e)
            )
