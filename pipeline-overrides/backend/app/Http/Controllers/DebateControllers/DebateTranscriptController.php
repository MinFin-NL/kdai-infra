<?php

namespace App\Http\Controllers\DebateControllers;

use Illuminate\Support\Facades\Log;
use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use App\Helpers\ResponseHelper;
use App\Events\TranscriptStartStopEvent;
use App\Http\Controllers\Controller;
use App\Services\IServices\IRoomService;
use App\Services\IServices\IMinIOService;
use App\Services\IServices\IDebateService;
use App\Services\IServices\IDebateTranscriptService;
use App\Services\IServices\IDebateEmulatorService;

class DebateTranscriptController extends Controller
{
    private IDebateTranscriptService $transcriptService;
    private IRoomService $roomService;
    private IDebateService $debateService;
    private IMinIOService $minIOService;
    private IDebateEmulatorService $debateEmulatorService;

    public function __construct(
        IDebateTranscriptService $transcriptService,
        IRoomService $roomService,
        IDebateService $debateService,
        IMinIOService $minIOService,
        IDebateEmulatorService $debateEmulatorService
    ) {
        $this->transcriptService = $transcriptService;
        $this->roomService = $roomService;
        $this->debateService = $debateService;
        $this->minIOService = $minIOService;
        $this->debateEmulatorService = $debateEmulatorService;
    }

    public function toggleStartStopTranscript(Request $request): JsonResponse
    {
        $validatedData = $request->validate([
            'debateID' => 'required|uuid',
        ], [
            'debateID.required' => 'debateID is verplicht!',
            'debateID.uuid' => 'debateID moet een UUID zijn!',
        ]);

        $debateID = $validatedData['debateID'];
        $debate = $this->debateService->getDebateByID($debateID);

        if (!$debate) {
            return ResponseHelper::error(404, 'Debate not found for the given debateID.');
        }

        if (!$this->transcriptService->getATTSHealthStatus()) {
            return ResponseHelper::error(503, 'ATTS service is currently unavailable.');
        }

        $debateStartTime = Carbon::parse($debate->date)
            ->startOfMinute()
            ->setTimezone('Europe/Amsterdam')
            ->subHours(2);
        $currentTime = Carbon::now('Europe/Amsterdam')->startOfMinute();

        if ($debateStartTime->isFuture()) {
            $minutesUntilDebate = $currentTime->diffInMinutes($debateStartTime);
            if ($minutesUntilDebate > 2) {
                return ResponseHelper::error(400, 'You can only transcribing when the debate starts within two minutes.');
            }
        }

        $updatedDebate = $this->debateService->toggleDebateStatus($debate);

        if ($updatedDebate->transcribe_status == 1) {
            $debateStreamURL = $this->getDebateStreamUrl($debateID);

            Log::info("Using debateStreamURL: {$debateStreamURL} for debateID: {$debateID}");

            $startTranscriptionData = [
                'debate_id' => $debateID,
                'm3u8_stream' => $debateStreamURL,
            ];

            $response = $this->transcriptService->startTranscription($startTranscriptionData);
            // Check if the response is valid and has a status code of 200
            if (($response['status'] ?? 500) !== 202) {
                return ResponseHelper::error(500, ['message' => 'Failed to start transcription', 'response' => $response]);
            }
        } else {
            $stopTranscriptionData = [
                'debate_id' => $debateID,
            ];

            $response = $this->transcriptService->stopTranscription($stopTranscriptionData);
            if (($response['status'] ?? 500) !== 202) {
                return ResponseHelper::error(500, ['message' => 'Failed to stop transcription', 'response' => $response]);
            }
        }

        $this->debateService->updateDebateByID($debateID, $updatedDebate);

        event(new TranscriptStartStopEvent($updatedDebate->id, $updatedDebate->transcribe_status));

        return ResponseHelper::success(202, [
            'transcriptStatus' => $updatedDebate->transcribe_status,
        ]);
    }

    private function getDebateStreamUrl(string $debateID): string
    {
        // Only use the internal M3U8 emulator if the user changed the value trough the web interface
        $emulatorStatus = $this->debateEmulatorService->getEmulatorStatus();
        if ($emulatorStatus === 'on') {
            return "http://kdai-m3u8-emulator:2121/hls/stream.m3u8";
        }

        $baseUrl = getenv('STREAM_BASE_URL');
        $audioPath = getenv('STREAM_AUDIO_PATH');
        $roomName = $this->roomService->getNormalizedRoomNameByDebateID($debateID);

        return "{$baseUrl}/{$roomName}/{$audioPath}";
    }

    public function getFullTranscript(Request $request): JsonResponse
    {
        $validatedData = $request->validate([
            'debateID' => 'required|uuid',
        ], [
            'debateID.required' => 'debateID is verplicht!',
            'debateID.uuid' => 'debateID moet een UUID zijn!',
        ]);

        $debateID = $validatedData['debateID'];
        $debate = $this->debateService->getDebateByID($debateID);

        if (!$debate) {
            return ResponseHelper::error(404, 'Debate not found for the given debateID.');
        }

        // PIPELINE OVERRIDE: rebuild the transcript from every per-segment file the ATTS
        // pipeline writes (TS/TFS write ".../transcripts/<segment>/filtered_transcript.txt" for
        // every segment). This makes the transcript durable and complete, so a browser that
        // reconnects or refreshes recovers the whole transcript-so-far -- not just the segments
        // the reviewer already confirmed (which is all the TCS-written full_transcript.txt held).
        // Segment folders are timestamped (YYYYMMDD_HHMMSSmmm), so a lexical sort is chronological.
        $files = $this->minIOService->listFiles("{$debateID}/transcripts");
        $segmentFiles = array_values(array_filter(
            $files,
            fn ($path) => str_ends_with($path, '/filtered_transcript.txt')
        ));
        sort($segmentFiles);

        $parts = [];
        foreach ($segmentFiles as $path) {
            $contents = trim($this->minIOService->getFileContents($path));
            if ($contents !== '') {
                $parts[] = $contents;
            }
        }
        $transcript = implode("\n", $parts);

        // Fall back to the consolidated full_transcript.txt (written by TCS on confirmation)
        // if no per-segment files exist yet.
        if ($transcript === '') {
            $fullPath = "{$debateID}/transcripts/full_transcript.txt";
            if ($this->minIOService->doesFileExist($fullPath)) {
                $transcript = trim($this->minIOService->getFileContents($fullPath));
            }
        }

        if ($transcript === '') {
            return ResponseHelper::error(204, 'Transcript not found for the given debateID.');
        }

        return ResponseHelper::success(200, [
            'segment_id' => "full_transcript",
            'transcript' => $transcript,
        ]);
    }
}
