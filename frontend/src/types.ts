export type Evidence = "verified" | "documented_model" | "documented_related" | "experimental" | "not_implemented";

export interface Pose { x: number; y: number; angle: number }
export interface Room { id: number; name: string; robot_name?: string; bbox: number[] }

export interface MapData {
  id?: number;
  source: string;
  simulated: boolean;
  timestamp: number;
  pixel_size: number;
  width: number;
  height: number;
  left: number;
  top: number;
  robot: Pose | null;
  charger: Pose | null;
  classes_b64: string;
  segments_b64: string;
  rooms: Room[];
  path: number[][][];
  virtual_walls: number[][];
  no_go_areas: number[][];
  no_mop_areas: number[][];
  has_saved_map: boolean;
  extra_keys: string[];
}

export interface Consumable { percent: number | null; hours_left: number | null }

export interface Status {
  simulated: boolean;
  timestamp: number;
  battery: number | null;
  charging_label: string | null;
  status: number | null;
  status_label: string | null;
  mode: number | null;
  mode_label: string | null;
  error: number | null;
  error_name: string | null;
  error_label: string | null;
  fan_speed: number | null;
  water_flow: number | null;
  cleaning_time_min: number | null;
  cleaning_area_m2: number | null;
  total_clean_time_min: number | null;
  total_clean_count: number | null;
  total_clean_area_m2: number | null;
  consumables: { main_brush: Consumable; side_brush: Consumable; filter: Consumable };
  volume: number | null;
  dnd: { enabled: boolean | null; start: string | null; stop: string | null };
  properties: {
    key: string; siid: number; piid: number; label: string; unit: string | null; code: number;
    value: unknown; display: unknown; evidence: Evidence; notes: string;
  }[];
}

export interface CommandInfo {
  id: string; label: string; evidence: Evidence; evidence_label: string; base_evidence: Evidence;
  sources: string[]; moves_robot: boolean; requires_confirmation: boolean; notes: string;
  siid: number | null; aiid: number | null; piid: number | null;
  verification: { worked: boolean; notes: string; firmware: string | null } | null;
}

export interface Capabilities {
  model: string;
  probe_available: boolean;
  probe_firmware: string | null;
  model_confirmed: boolean | null;
  allow_experimental: boolean;
  commands: CommandInfo[];
  properties: {
    key: string; siid: number; piid: number; label: string; access: string; evidence: Evidence;
    evidence_label: string; sources: string[]; notes: string; unit: string | null;
  }[];
}

export interface AppState {
  simulated: boolean;
  settings: {
    mode: "simulator" | "real"; robot_ip: string; robot_did: string; cloud_server: string;
    allow_experimental: boolean; poll_interval_s: number; auto_map_refresh: boolean; map_refresh_interval_s: number;
  };
  connection: { state: string; error: string | null; since: number };
  has_token: boolean;
  has_cloud_session: boolean;
  secrets_persistent: boolean;
  cloud_servers: string[];
}

export interface Region { id: number; name: string; kind: "zone" | "point" | "room_sequence"; data: any; updated: number }
export interface Draft { id: number; name: string; kind: "virtual_wall" | "no_go" | "no_mop"; data: any; robot_recognized: boolean }
