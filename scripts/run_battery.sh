#!/usr/bin/env bash
# =============================================================================
# IAC — Bateria de testes LLM
# =============================================================================
# Executa os 3 modos (single, multi, loop) para cada modelo informado.
# Logs salvos em .iac/logs/<backend>/<modelo>_{single,multi,loop}.log
# Se já existirem logs, move para subpasta com datahora.
#
# Uso:
#   ./scripts/run_battery.sh --base-dir /caminho/projeto --models "modelo1,modelo2"
#   ./scripts/run_battery.sh --base-dir /caminho/projeto --models "llama-3.1-8b-instant,llama-3.3-70b-versatile"
#   ./scripts/run_battery.sh --base-dir /caminho/projeto --models "llama-3.1-8b-instant" --issue-url URL
#
# Requer:
#   - .iac/.env configurado (GITLAB_TOKEN, IAC_LLM_BACKEND, API key)
#   - iac instalado (pip install -e .)

set -euo pipefail

# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------

BASE_DIR="."
MODELS=""
ISSUE_URL=""
MODES="single multi loop"

while [[ $# -gt 0 ]]; do
    case $1 in
        --base-dir) BASE_DIR="$2"; shift 2 ;;
        --models) MODELS="$2"; shift 2 ;;
        --issue-url) ISSUE_URL="$2"; shift 2 ;;
        --modes) MODES="$2"; shift 2 ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

if [[ -z "$MODELS" ]]; then
    echo "Uso: $0 --base-dir DIR --models 'modelo1,modelo2' --issue-url URL"
    echo ""
    echo "Exemplo:"
    echo "  $0 --base-dir /home/user/suap --models 'llama-3.1-8b-instant,llama-3.3-70b-versatile' \\"
    echo "     --issue-url https://gitlab.example.com/project/-/work_items/16118"
    exit 1
fi

if [[ -z "$ISSUE_URL" ]]; then
    echo "Erro: --issue-url é obrigatório"
    exit 1
fi

BASE_DIR=$(realpath "$BASE_DIR")
IAC_DIR="$BASE_DIR/.iac"
LOGS_DIR="$IAC_DIR/logs"

if [[ ! -d "$IAC_DIR" ]]; then
    echo "Erro: $IAC_DIR não encontrado. Execute 'iac init' primeiro."
    exit 1
fi

# Detectar backend do .env
BACKEND=$(grep -E "^IAC_LLM_BACKEND=" "$IAC_DIR/.env" 2>/dev/null | cut -d= -f2 || echo "groq")

# ---------------------------------------------------------------------------
# Funções
# ---------------------------------------------------------------------------

# Nome curto para diretório (remove prefixos e caracteres especiais)
model_dir_name() {
    local model="$1"
    echo "$model" | sed 's|.*/||' | sed 's|[:/]|_|g'
}

# Backup de logs existentes
backup_existing_logs() {
    local model_logs_dir="$1"
    if [[ -d "$model_logs_dir" ]] && ls "$model_logs_dir"/*.log &>/dev/null; then
        local backup_name
        backup_name=$(date +"%Y%m%d_%H%M%S")
        local backup_dir="$model_logs_dir/$backup_name"
        mkdir -p "$backup_dir"
        mv "$model_logs_dir"/*.log "$backup_dir/" 2>/dev/null || true
        echo "  Logs anteriores movidos para $backup_name/"
    fi
}

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

echo "=============================================="
echo " IAC — Bateria de testes LLM"
echo "=============================================="
echo " Base dir:  $BASE_DIR"
echo " Backend:   $BACKEND"
echo " Issue URL: $ISSUE_URL"
echo " Modelos:   $MODELS"
echo " Modos:     $MODES"
echo "=============================================="
echo ""

IFS=',' read -ra MODEL_LIST <<< "$MODELS"
TOTAL_SCENARIOS=$(( ${#MODEL_LIST[@]} * $(echo "$MODES" | wc -w) ))
CURRENT=0
RESULTS=""

for MODEL in "${MODEL_LIST[@]}"; do
    MODEL=$(echo "$MODEL" | xargs)  # trim
    DIR_NAME=$(model_dir_name "$MODEL")
    MODEL_LOGS="$LOGS_DIR/$DIR_NAME"

    echo "=== $MODEL ==="

    # Backup logs existentes
    mkdir -p "$MODEL_LOGS"
    backup_existing_logs "$MODEL_LOGS"

    for MODE in $MODES; do
        CURRENT=$((CURRENT + 1))
        echo "--- [$CURRENT/$TOTAL_SCENARIOS] $DIR_NAME $MODE ---"

        # Executar análise
        OUTPUT=$(iac analyze \
            --base-dir "$BASE_DIR" \
            --issue-url "$ISSUE_URL" \
            --llm "$BACKEND" \
            --llm-model "$MODEL" \
            --mode "$MODE" 2>&1)

        # Extrair classificação do output
        CLASSIFICACAO=$(echo "$OUTPUT" | grep "^Classificação:" | head -1 || true)
        SUBCLASSIFICACAO=$(echo "$OUTPUT" | grep "^Subclassificação:" | head -1 || true)
        LABELS=$(echo "$OUTPUT" | grep "^Labels sugeridos:" | head -1 || true)

        echo "  $CLASSIFICACAO"
        [[ -n "$SUBCLASSIFICACAO" ]] && echo "  $SUBCLASSIFICACAO"
        echo "  $LABELS"

        # Mover log gerado
        LATEST_LOG=$(ls -t "$LOGS_DIR"/iac_2026*.log 2>/dev/null | head -1)
        if [[ -n "$LATEST_LOG" ]]; then
            mv "$LATEST_LOG" "$MODEL_LOGS/${DIR_NAME}_${MODE}.log"
        fi

        # Registrar resultado
        RESULTS+="| $DIR_NAME | $MODE | $CLASSIFICACAO | $LABELS |\n"
    done
    echo ""
done

echo "=============================================="
echo " BATERIA COMPLETA — $TOTAL_SCENARIOS cenários"
echo "=============================================="
echo ""
echo "| Modelo | Modo | Classificação | Labels |"
echo "|--------|------|---------------|--------|"
echo -e "$RESULTS"
echo ""
echo "Logs em: $LOGS_DIR/"
ls -d "$LOGS_DIR"/*/  2>/dev/null
