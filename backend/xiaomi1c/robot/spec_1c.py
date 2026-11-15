"""Base de conhecimento MIoT do Xiaomi Robot Vacuum-Mop 1C (``dreame.vacuum.mc1808``).

Cada propriedade/comando traz o **nível de evidência** e as **fontes**. Nada aqui
é considerado "comprovado no seu robô" até que o diagnóstico (``xiaomi1c probe``)
leia a propriedade com sucesso no seu equipamento — esse resultado fica salvo
no banco local e é combinado com esta tabela em tempo de execução.

Níveis de evidência
-------------------
``verified``            Comprovado no SEU robô (resultado do probe / teste real).
``documented_model``    Documentado para o mc1808 por fontes independentes, mas
                        ainda não testado no seu equipamento.
``documented_related``  Documentado apenas para modelos Dreame relacionados.
``experimental``        Relatos da comunidade, divergentes ou incompletos.
``not_implemented``     Sem comando conhecido para o firmware original.

Fontes (abreviações usadas em ``sources``)
------------------------------------------
* ``python-miio``  rytilahti/python-miio – ``integrations/(vacuum/)dreame/dreamevacuum_miot.py``
* ``piotras1``     Piotras1/dreame-vacuum-1808-1c – ``custom_components/dreame_mc1808/dreame_client.py``
* ``al-one#279``   al-one/hass-xiaomi-miot issue #279 (limpeza por cômodo, relatada como funcional)
* ``al-one#1506``  al-one/hass-xiaomi-miot issue #1506 (mesma chamada, falha -1 por JSON mal formatado)
* ``card#406``     PiotrMachowski/lovelace-xiaomi-vacuum-map-card discussion #406 (zona/cômodo)
* ``tasshack``     Tasshack/dreame-vacuum – formato de paredes virtuais em modelos Dreame NOVOS (siid 6)
* ``map-extractor`` PiotrMachowski/...-Xiaomi-Cloud-Map-Extractor – formato de mapa Dreame
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MODEL = "dreame.vacuum.mc1808"
MIOT_URN = "urn:miot-spec-v2:device:vacuum:0000A006:dreame-mc1808:1"


class Evidence(str, Enum):
    VERIFIED = "verified"
    DOCUMENTED_MODEL = "documented_model"
    DOCUMENTED_RELATED = "documented_related"
    EXPERIMENTAL = "experimental"
    NOT_IMPLEMENTED = "not_implemented"


EVIDENCE_LABELS_PT = {
    Evidence.VERIFIED: "Comprovado no seu robô",
    Evidence.DOCUMENTED_MODEL: "Documentado para o mc1808 (não testado no seu robô)",
    Evidence.DOCUMENTED_RELATED: "Documentado só para modelos relacionados",
    Evidence.EXPERIMENTAL: "Experimental",
    Evidence.NOT_IMPLEMENTED: "Não implementado / sem comando conhecido",
}


# --------------------------------------------------------------------------- enums
DEVICE_STATUS = {  # siid 3 / piid 2
    1: "Aspirando",
    2: "Ocioso",
    3: "Pausado",
    4: "Erro",
    5: "Voltando à base",
    6: "Carregando",
    7: "Passando pano",
    13: "Limpeza manual",
}

CHARGING_STATE = {  # siid 2 / piid 2
    1: "Carregando",
    2: "Não está carregando",
    4: "Carregando (2)",
    5: "Indo carregar",
}

OPERATING_MODE = {  # siid 18 / piid 1
    1: "Pausado",
    2: "Limpando",
    3: "Indo carregar",
    6: "Carregando",
    13: "Limpeza manual",
    14: "Dormindo",
    17: "Manual pausado",
    18: "Limpeza por cômodo",
    19: "Limpeza por zona",
}

FAN_SPEED = {0: "Silencioso", 1: "Padrão", 2: "Médio", 3: "Forte"}  # siid 18 / piid 6
WATER_FLOW = {1: "Baixo", 2: "Médio", 3: "Alto"}  # siid 18 / piid 20

ERROR_CODES = {  # siid 3 / piid 1 — tabela do piotras1 (nomes do firmware)
    0: ("NoError", "Sem erro"),
    1: ("Drop", "Roda suspensa / robô levantado"),
    2: ("Cliff", "Sensor de queda (cliff) acionado"),
    3: ("Bumper", "Para-choque preso"),
    4: ("Gesture", "Robô inclinado"),
    5: ("Bumper_repeat", "Para-choque acionado repetidamente"),
    6: ("Drop_repeat", "Roda suspensa repetidamente"),
    7: ("Optical_flow", "Erro no sensor de fluxo óptico"),
    8: ("No_box", "Reservatório de pó ausente"),
    9: ("No_tankbox", "Tanque de água ausente"),
    10: ("Waterbox_empty", "Tanque de água vazio"),
    11: ("Box_full", "Reservatório de pó cheio"),
    12: ("Brush", "Escova principal travada"),
    13: ("Side_brush", "Escova lateral travada"),
    14: ("Fan", "Falha no ventilador"),
    15: ("Left_wheel_motor", "Motor da roda esquerda"),
    16: ("Right_wheel_motor", "Motor da roda direita"),
    17: ("Turn_suffocate", "Robô preso ao girar"),
    18: ("Forward_suffocate", "Robô preso ao avançar"),
    19: ("Charger_get", "Não encontrou a base"),
    20: ("Battery_low", "Bateria baixa"),
    21: ("Charge_fault", "Falha de carregamento"),
    22: ("Battery_percentage", "Erro no nível de bateria"),
    23: ("Heart", "Erro interno (heartbeat)"),
    24: ("Camera_occlusion", "Câmera obstruída"),
    25: ("Camera_fault", "Falha na câmera"),
    26: ("Event_battery", "Evento de bateria"),
    27: ("Forward_looking", "Sensor frontal"),
    28: ("Gyroscope", "Erro no giroscópio"),
}


# --------------------------------------------------------------------------- properties
@dataclass(frozen=True)
class Prop:
    key: str
    siid: int
    piid: int
    label: str
    access: str  # combinação de r/w/n
    evidence: Evidence
    sources: tuple[str, ...]
    unit: str | None = None
    enum: dict[int, Any] | None = None
    notes: str = ""

    @property
    def writable(self) -> bool:
        return "w" in self.access


P = Prop
E = Evidence
PROPERTIES: tuple[Prop, ...] = (
    P("battery_level", 2, 1, "Bateria", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "%"),
    P("charging_state", 2, 2, "Estado de carga", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), enum=CHARGING_STATE),
    P("device_fault", 3, 1, "Código de erro", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"),
      enum={k: v[1] for k, v in ERROR_CODES.items()}),
    P("device_status", 3, 2, "Estado operacional", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), enum=DEVICE_STATUS),
    P("operating_mode", 18, 1, "Modo de trabalho", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), enum=OPERATING_MODE),
    P("cleaning_time", 18, 2, "Tempo da limpeza atual", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "min"),
    P("cleaning_area_18_3", 18, 3, "Área limpa (18.3)", "rw", E.EXPERIMENTAL, ("piotras1",), "m²",
      notes="piotras1 lê a área em 18.3; python-miio em 18.4. O probe define qual responde."),
    P("cleaning_area", 18, 4, "Área limpa (18.4)", "rn", E.EXPERIMENTAL, ("python-miio",), "m²",
      notes="Ver 18.3 — fontes divergem."),
    P("fan_speed", 18, 6, "Potência de sucção", "rwn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), enum=FAN_SPEED),
    P("delete_timer", 18, 8, "delete-timer", "w", E.DOCUMENTED_MODEL, ("python-miio",),
      notes="Somente escrita; não é lido pelo status."),
    P("water_box", 18, 9, "Tanque de água/pano instalado", "n", E.EXPERIMENTAL, ("python-miio", "piotras1"),
      notes="Spec indica apenas notify; pode não responder a leitura."),
    P("first_clean_time", 18, 12, "Primeira limpeza (epoch)", "rn", E.DOCUMENTED_MODEL, ("python-miio",)),
    P("total_clean_time", 18, 13, "Tempo total de limpeza", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "min"),
    P("total_clean_times", 18, 14, "Quantidade total de limpezas", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("total_clean_area", 18, 15, "Área total limpa", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "m²"),
    P("total_log_start", 18, 16, "total-log-start", "rn", E.EXPERIMENTAL, ("piotras1",)),
    P("button_led", 18, 17, "LED do botão", "rn", E.EXPERIMENTAL, ("piotras1",)),
    P("clean_success", 18, 18, "Última limpeza concluída", "rn", E.EXPERIMENTAL, ("piotras1",)),
    P("water_flow", 18, 20, "Fluxo de água (pano)", "rn", E.EXPERIMENTAL, ("piotras1",), enum=WATER_FLOW,
      notes="python-miio marca como TODO no 1C; piotras1 lê, mas a escrita não está documentada."),
    P("life_sieve", 19, 1, "Vida útil (filtro/peneira) — bruto", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("life_brush_side", 19, 2, "Vida útil escova lateral — bruto", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("life_brush_main", 19, 3, "Vida útil escova principal — bruto", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("dnd_enabled", 20, 1, "Não perturbe ativo", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("dnd_start", 20, 2, "Não perturbe — início", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("dnd_stop", 20, 3, "Não perturbe — fim", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("map_view", 23, 1, "map-view", "rn", E.EXPERIMENTAL, ("python-miio", "piotras1"),
      notes="Conteúdo desconhecido no 1C; o probe registra o valor bruto."),
    P("frame_info", 23, 2, "frame-info", "w", E.EXPERIMENTAL, ("python-miio",)),
    P("volume", 24, 1, "Volume", "rwn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "%"),
    P("voice_package", 24, 3, "Pacote de voz", "rw", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("timezone", 25, 1, "Fuso horário", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1")),
    P("main_brush_left", 26, 1, "Escova principal — horas restantes", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "h"),
    P("main_brush_life", 26, 2, "Escova principal — vida útil", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "%"),
    P("filter_life", 27, 1, "Filtro — vida útil", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "%"),
    P("filter_left", 27, 2, "Filtro — horas restantes", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "h"),
    P("side_brush_left", 28, 1, "Escova lateral — horas restantes", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "h"),
    P("side_brush_life", 28, 2, "Escova lateral — vida útil", "rn", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), "%"),
)
del P, E

PROPS_BY_KEY = {p.key: p for p in PROPERTIES}
READABLE_PROPS = tuple(p for p in PROPERTIES if "r" in p.access or "n" in p.access)


# --------------------------------------------------------------------------- commands
@dataclass(frozen=True)
class Command:
    id: str
    label: str
    evidence: Evidence
    sources: tuple[str, ...]
    moves_robot: bool  # inicia movimento/limpeza => exige confirmação explícita
    requires_confirmation: bool
    kind: str  # "action" | "set" | "composite" | "none"
    siid: int | None = None
    aiid: int | None = None
    piid: int | None = None
    notes: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)


C = Command
E = Evidence
COMMANDS: tuple[Command, ...] = (
    C("start", "Iniciar limpeza completa", E.DOCUMENTED_MODEL, ("python-miio",), True, True, "action", 3, 1,
      notes="start-sweep (3.1). piotras1 usa 18.1 com piid1=2 como alternativa."),
    C("stop", "Interromper limpeza", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, False, "action", 3, 2,
      notes="stop-sweeping (3.2)."),
    C("pause", "Pausar", E.EXPERIMENTAL, ("piotras1",), False, False, "action", 18, 2,
      notes="O 1C não tem ação 'pause' documentada; 18.2 (stop-clean) é usado como pausa. Verificar se retoma."),
    C("resume", "Continuar", E.EXPERIMENTAL, ("python-miio",), True, True, "action", 3, 1,
      notes="Reenvia start-sweep; espera-se que o firmware retome a tarefa pausada — a confirmar."),
    C("home", "Voltar para a base", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), True, True, "action", 2, 1,
      notes="start-charge (2.1)."),
    C("locate", "Localizar (tocar som)", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, False, "action", 17, 1),
    C("test_sound", "Testar som", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, False, "action", 24, 3),
    C("set_fan_speed", "Definir potência de sucção", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, False,
      "set", 18, None, 6, params_schema={"value": {"type": "int", "enum": FAN_SPEED}}),
    C("set_volume", "Definir volume", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, False,
      "set", 24, None, 1, params_schema={"value": {"type": "int", "min": 0, "max": 100}}),
    C("set_water_flow", "Definir fluxo de água", E.EXPERIMENTAL, ("piotras1",), False, True,
      "set", 18, None, 20, params_schema={"value": {"type": "int", "enum": WATER_FLOW}},
      notes="Escrita NÃO documentada para o 1C (spec indica leitura). Pode ser rejeitada pelo firmware."),
    C("set_dnd", "Configurar 'não perturbe'", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, True,
      "composite", 20, params_schema={"enabled": {"type": "bool"}, "start": {"type": "HH:MM"}, "stop": {"type": "HH:MM"}}),
    C("reset_main_brush", "Zerar contador da escova principal", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, True, "action", 26, 1),
    C("reset_filter", "Zerar contador do filtro", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, True, "action", 27, 1),
    C("reset_side_brush", "Zerar contador da escova lateral", E.DOCUMENTED_MODEL, ("python-miio", "piotras1"), False, True, "action", 28, 1),
    C("clean_zone", "Limpar zona(s) retangular(es)", E.EXPERIMENTAL, ("card#406", "piotras1"), True, True, "action", 18, 1,
      notes='18.1 com piid1=19 e piid21=\'{"areas":[[x1,y1,x2,y2,repetições,1,1]]}\' (mm, coordenadas do mapa). '
            "Os dois últimos campos têm significado não confirmado. Sem relato publicado de sucesso no 1C.",
      params_schema={"zones": {"type": "list[[x1,y1,x2,y2]]"}, "repeats": {"type": "int", "min": 1, "max": 3}}),
    C("clean_rooms", "Limpar cômodo(s)", E.EXPERIMENTAL, ("al-one#279", "card#406", "al-one#1506", "piotras1"), True, True,
      "action", 18, 1,
      notes='18.1 com piid1=18 e piid21=\'{"selects":[[id,repetições,sucção,3,ordem]]}\'. Relatos: funcionou (2021/2024) '
            'e "sucesso sem movimento" (2025). Exige mapa salvo com cômodos.',
      params_schema={"rooms": {"type": "list[int]"}, "repeats": {"type": "int"}, "fan_speed": {"type": "int"}}),
    C("clean_point", "Limpar ao redor de um ponto", E.EXPERIMENTAL, ("card#406",), True, True, "composite", 18, 1,
      notes="Não há 'limpeza por ponto' documentada no 1C. EMULADO como zona quadrada centrada no ponto clicado.",
      params_schema={"x": {"type": "int"}, "y": {"type": "int"}, "size": {"type": "int", "default": 1000}}),
    C("request_map_upload", "Pedir upload do mapa à Cloud", E.EXPERIMENTAL, ("piotras1", "tasshack"), False, False,
      "action", 23, 1, notes="Análogo à ação 6.1 dos modelos novos. Não move o robô."),
    C("remote_move", "Movimento manual (controle remoto)", E.EXPERIMENTAL, ("python-miio",), True, True, "action", 21, 1,
      notes="python-miio envia 21.1 com piid1=ângulo, piid2=velocidade; piotras1 trata 21.1 como 'start remote'. Divergente."),
    C("set_virtual_walls", "Gravar paredes virtuais / zonas proibidas no robô", E.NOT_IMPLEMENTED, ("tasshack",), False, True, "none",
      notes="Nenhum comando documentado para o 1C. Nos Dreame novos é 6.2 com piid4='{\"vw\":{...}}'. "
            "O app só LÊ as restrições existentes (campo 'vw' do mapa) e permite rascunhos locais."),
    C("edit_rooms", "Dividir/unir/renomear cômodos no robô", E.NOT_IMPLEMENTED, (), False, True, "none",
      notes="Sem comando conhecido para o 1C. Nomes personalizados ficam só no app."),
    C("edit_navigation_map", "Alterar o mapa interno de navegação", E.NOT_IMPLEMENTED, (), False, True, "none",
      notes="O firmware original não aceita mapas externos. Só seria possível com root (Valetudo), fora do escopo."),
)
del C, E

COMMANDS_BY_ID = {c.id: c for c in COMMANDS}


def describe_value(prop: Prop, value: Any) -> Any:
    """Converte valor bruto em rótulo legível quando houver enum."""
    if prop.enum is not None and isinstance(value, int):
        return prop.enum.get(value, f"Desconhecido ({value})")
    return value


def zone_payload(zones: list[list[int]], repeats: int = 1, extra: tuple[int, int] = (1, 1)) -> list[dict[str, Any]]:
    """Monta o payload de limpeza por zona (formato card#406)."""
    import json

    if not zones:
        raise ValueError("Informe ao menos uma zona")
    if not 1 <= repeats <= 3:
        raise ValueError("Repetições devem estar entre 1 e 3")
    areas = []
    for z in zones:
        if len(z) != 4:
            raise ValueError("Cada zona deve ter [x1, y1, x2, y2]")
        x1, y1, x2, y2 = (int(v) for v in z)
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        if x2 - x1 < 300 or y2 - y1 < 300:
            raise ValueError("Zona muito pequena (mínimo 30 cm x 30 cm)")
        areas.append([x1, y1, x2, y2, repeats, *extra])
    return [
        {"piid": 1, "value": 19},
        {"piid": 21, "value": json.dumps({"areas": areas}, separators=(",", ":"))},
    ]


def rooms_payload(rooms: list[int], repeats: int = 1, fan_speed: int = 1, mop_mode: int = 3) -> list[dict[str, Any]]:
    """Monta o payload de limpeza por cômodo (formato al-one#279 / card#406).

    O JSON é enviado minificado como *string* — enviar objeto causa erro -1 (al-one#1506).
    """
    import json

    if not rooms:
        raise ValueError("Informe ao menos um cômodo")
    if fan_speed not in FAN_SPEED:
        raise ValueError("Potência inválida")
    selects = [[int(r), int(repeats), int(fan_speed), int(mop_mode), i + 1] for i, r in enumerate(rooms)]
    return [
        {"piid": 1, "value": 18},
        {"piid": 21, "value": json.dumps({"selects": selects}, separators=(",", ":"))},
    ]


def point_to_zone(x: int, y: int, size: int = 1000) -> list[int]:
    """Emula limpeza por ponto: quadrado de ``size`` mm centrado em (x, y)."""
    size = max(500, min(int(size), 3000))
    h = size // 2
    return [int(x) - h, int(y) - h, int(x) + h, int(y) + h]
