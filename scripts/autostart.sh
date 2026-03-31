#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${ROOT_DIR}/state"
LOG_FILE="${STATE_DIR}/vk-openclaw.log"
API_PID_FILE="${STATE_DIR}/api.pid"
WORKER_PID_FILE="${STATE_DIR}/worker.pid"
GATEWAY_HOST="127.0.0.1"
GATEWAY_PORT="18789"
TIMEOUT_SECONDS="60"

mkdir -p "${STATE_DIR}"

load_env() {
  if [[ -f "${ROOT_DIR}/.env.local" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env.local"
    set +a
  else
    echo "Missing ${ROOT_DIR}/.env.local"
    return 1
  fi
}

is_running() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "${pid_file}")"
  kill -0 "${pid}" >/dev/null 2>&1
}

wait_for_gateway() {
  local start_ts now elapsed
  start_ts="$(date +%s)"
  while true; do
    if (echo >"/dev/tcp/${GATEWAY_HOST}/${GATEWAY_PORT}") >/dev/null 2>&1; then
      return 0
    fi
    now="$(date +%s)"
    elapsed="$((now - start_ts))"
    if [[ "${elapsed}" -ge "${TIMEOUT_SECONDS}" ]]; then
      echo "Gateway not reachable at ws://${GATEWAY_HOST}:${GATEWAY_PORT}"
      return 1
    fi
    sleep 2
  done
}

start_services() {
  load_env
  wait_for_gateway
  if is_running "${API_PID_FILE}" || is_running "${WORKER_PID_FILE}"; then
    echo "Services already running"
    return 1
  fi
  nohup python -m vk_openclaw_service.cli run-api --host 127.0.0.1 --port 8000 >>"${LOG_FILE}" 2>&1 &
  echo $! >"${API_PID_FILE}"
  nohup python -m vk_openclaw_service.cli run-worker --interval-seconds 5 >>"${LOG_FILE}" 2>&1 &
  echo $! >"${WORKER_PID_FILE}"
  echo "Started API PID $(cat "${API_PID_FILE}") and worker PID $(cat "${WORKER_PID_FILE}")"
}

stop_services() {
  local ok=0
  if is_running "${WORKER_PID_FILE}"; then
    kill "$(cat "${WORKER_PID_FILE}")" || ok=1
  fi
  if is_running "${API_PID_FILE}"; then
    kill "$(cat "${API_PID_FILE}")" || ok=1
  fi
  rm -f "${WORKER_PID_FILE}" "${API_PID_FILE}"
  [[ "${ok}" -eq 0 ]] && echo "Stopped services" || echo "Stop completed with warnings"
  return "${ok}"
}

status_services() {
  if is_running "${API_PID_FILE}"; then
    echo "api: running (pid $(cat "${API_PID_FILE}"))"
  else
    echo "api: down"
  fi
  if is_running "${WORKER_PID_FILE}"; then
    echo "worker: running (pid $(cat "${WORKER_PID_FILE}"))"
  else
    echo "worker: down"
  fi
  echo "log: ${LOG_FILE}"
}

case "${1:-}" in
  start) start_services ;;
  stop) stop_services ;;
  status) status_services ;;
  restart) stop_services || true; start_services ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
