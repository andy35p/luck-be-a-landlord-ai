"""Print read-only advice changes; never sends input or modifies game files."""
import argparse
import json
import time
from luck_agent.evaluation.live_feed import LiveFeed
from luck_agent.evaluation.advice_display import publish
from luck_agent.evaluation.live_run import ProcessProbe, RunLog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--display-file', help='Optional display-only JSON sidecar')
    parser.add_argument('--event-log', help='New JSONL file for timestamped run diagnostics')
    parser.add_argument('--game-pid', type=int, help='Monitor this existing Windows process; never launch or terminate it')
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600: parser.error('seconds must be in (0, 3600]')
    if args.game_pid is not None and args.game_pid <= 0: parser.error('game-pid must be positive')
    log = RunLog(args.event_log)
    probe, feed = None, None
    outcome = 'error'
    try:
        log.emit('started', requested_seconds=args.seconds, game_pid=args.game_pid)
        if args.game_pid is not None: probe = ProcessProbe(args.game_pid)
        feed = LiveFeed(args.directory)
        end, previous = time.monotonic()+args.seconds, None
        while time.monotonic() < end:
            if probe is not None:
                exit_code = probe.poll()
                if exit_code is not None:
                    log.emit('game_exited', exit_code=exit_code)
                    outcome = 'game_exited'
                    break
            advice = feed.poll()
            if args.display_file:
                if publish(args.display_file, advice, feed.last_identity) is None:
                    log.emit('display_write_busy')
            result = json.dumps(advice, ensure_ascii=False, sort_keys=True)
            if result != previous:
                print(result, flush=True)
                log.emit('advice_changed', advice=advice, identity=feed.last_identity)
                previous = result
            time.sleep(.1)
        else:
            outcome = 'duration_completed'
    except KeyboardInterrupt:
        outcome = 'interrupted'
        raise
    except Exception as exc:
        log.emit('error', error_type=type(exc).__name__, message=str(exc))
        raise
    finally:
        try:
            if args.display_file:
                value = publish(args.display_file, {'status': 'unavailable', 'reasons': ['feed_stalled']}, feed.last_identity if feed else None)
                log.emit('display_offline', published=value is not None)
        finally:
            if probe: probe.close()
            log.emit('finished', outcome=outcome)
            log.close()


if __name__ == '__main__': main()
