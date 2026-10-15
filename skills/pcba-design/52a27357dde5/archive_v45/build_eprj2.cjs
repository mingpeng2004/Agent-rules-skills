/**
 * PCBA Skill v4.0 — .eprj2 回写脚本模板
 * 用法: 复制此脚本到项目 scripts/ 目录, 填写 COMPONENT_DEFS 与 PCB_LINES/SCH_LINES,
 *       然后运行 NODE_PATH=./node_modules node scripts/build_eprj2.cjs
 *
 * 前置依赖: npm install better-sqlite3
 */
const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '..', '<PROJECT>.eprj2');   // TODO: 替换为实际项目名
const BACKUP = path.resolve(__dirname, '..', '<PROJECT>.backup.eprj2');
const TARGET = SRC;

// ============================================================
// TODO: 用户填入 Phase 3 元件 + Phase 4 走线 + Phase 3 丝印
// ============================================================
const COMPONENT_DEFS = [
  // { ref: 'J1', type: 'Connector_SMD', x: 0, y: -7, layerId: 0, footprint: 'GH1.25-6P' },
];

// ============================================================
// JSON Lines Builder (按 format/pcb/*.md 公开规范)
// ============================================================
let eid = 1;
const nextEid = () => 'e' + (eid++);
let zIndex = 1.0;

function buildPcbBlob(pcbUuid) {
  const lines = [];
  lines.push(`{ "type": "DOCHEAD", "ticket": 1 }||{ "docType": "PCB", "uuid": "${pcbUuid}", "client": "AI-Skill-v4.0" }|`);
  lines.push('{ "type": "CANVAS", "ticket": 1 }||{ "originX":0, "originY":0, "unit":"mm", "gridXSize":1, "gridYSize":1, "snapXSize":0.1, "snapYSize":0.1 }|');

  // 2 层板: Top + Bottom + Silks + Mask + Paste + Outline
  const layers = [
    { id: 0, layerType: 'TOP' }, { id: 2, layerType: 'BOTTOM' },
    { id: 3, layerType: 'TOP_SILK' }, { id: 4, layerType: 'BOT_SILK' },
    { id: 5, layerType: 'TOP_SOLDER_MASK' }, { id: 6, layerType: 'BOT_SOLDER_MASK' },
    { id: 7, layerType: 'TOP_PASTE_MASK' }, { id: 11, layerType: 'OUTLINE' },
  ];
  layers.forEach(L => lines.push(`{ "type": "LAYER", "id": ${L.id}, "ticket": 1 }||{ "layerType":"${L.layerType}", "layerName":"${L.layerType}", "status":3 }|`));
  lines.push('{ "type": "ACTIVE_LAYER", "ticket": 1 }||{ "layerId":0 }|');

  // 元件
  COMPONENT_DEFS.forEach(c => {
    const cid = nextEid();
    lines.push(`{ "type": "COMPONENT", "id":"${cid}", "ticket": 1 }||{ "partitionId":null, "groupId":0, "locked":1, "zIndex":${(zIndex+=0.1).toFixed(3)}, "layerId":${c.layerId}, "positionX":${c.x}, "positionY":${c.y}, "angle":0, "attrs":{ "Designator":"${c.ref}", "Footprint":"${c.footprint}" } }|`);
  });

  // TODO: 走线 LINE + 丝印 STRING + 板框 + 铺铜 POUR
  // 参考 scripts/build_eprj2.js 完整实现

  lines.push('M02*');
  return lines.join('\n');
}

function buildSchBlob(schUuid) {
  const lines = [];
  lines.push(`{ "type": "DOCHEAD", "ticket": 1 }||{ "docType": "SCHEMATIC", "uuid": "${schUuid}", "client": "AI-Skill-v4.0" }|`);
  lines.push('{ "type": "CANVAS", "ticket": 1 }||{ "originX":0, "originY":0, "unit":"mm", "gridXSize":1, "gridYSize":1, "snapXSize":1, "snapYSize":1 }|');
  // TODO: 添加 COMPONENT + ATTR + WIRE + NETFLAG
  lines.push('M02*');
  return lines.join('\n');
}

// ============================================================
// 主流程
// ============================================================
function main() {
  if (!fs.existsSync(BACKUP)) {
    fs.copyFileSync(SRC, BACKUP);
    console.log('[BACKUP] ' + BACKUP);
  }
  const db = new Database(TARGET);
  const project = db.prepare('SELECT * FROM projects LIMIT 1').get();
  const project_uuid = project.uuid;
  const branch_uuid = project.branch_uuid;
  const ps = db.prepare('SELECT structure FROM project_structures WHERE branch_uuid=? LIMIT 1').get(branch_uuid);
  const structure = JSON.parse(ps.structure);
  const PCB_UUID = Object.keys(structure.pcbs)[0];
  const SCH_UUID = Object.keys(structure.schematics)[0];
  const SHEET_UUID = Object.keys(structure.sheets)[0];

  const PCB_BLOB = buildPcbBlob(PCB_UUID);
  const SCH_BLOB = buildSchBlob(SHEET_UUID);

  // 清空 + 写入
  ['coppers','texts','components','attributes','documents','boards','schematics'].forEach(t => {
    try { db.exec(`DELETE FROM ${t}`); } catch(e) {}
  });
  db.prepare('INSERT INTO boards (project_uuid, sch_uuid, name, sort) VALUES (?, ?, ?, ?)')
    .run(project_uuid, SCH_UUID, 'Board1', 1);
  db.prepare(`INSERT INTO schematics (uuid, description, ticket, sheet_count, project_uuid, name, display_name, createtime, updatetime, sort)
              VALUES (?, ?, 1, 1, ?, ?, ?, ?, ?, ?)`)
    .run(SCH_UUID, 'Schematic', project_uuid, 'Schematic1', 'Schematic1', Date.now(), Date.now(), '1');

  db.prepare(`INSERT INTO documents (uuid, title, display_title, description, docType, dataStr, sheet_id, ticket, sort_ticket, created_at, updated_at, schematic_uuid, project_uuid, image)
              VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?)`)
    .run(PCB_UUID, 'PCB1', 'PCB1', 'PCB', 2, PCB_BLOB, 0,
         new Date().toISOString().slice(0,19).replace('T',' '),
         new Date().toISOString().slice(0,19).replace('T',' '),
         null, project_uuid, null);
  db.prepare(`INSERT INTO documents (uuid, title, display_title, description, docType, dataStr, sheet_id, ticket, sort_ticket, created_at, updated_at, schematic_uuid, project_uuid, image)
              VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?)`)
    .run(SHEET_UUID, 'P1', 'P1', 'Schematic', 1, SCH_BLOB, 1,
         new Date().toISOString().slice(0,19).replace('T',' '),
         new Date().toISOString().slice(0,19).replace('T',' '),
         SCH_UUID, project_uuid, null);

  COMPONENT_DEFS.forEach(c => {
    const cuuid = 'comp_' + c.ref.toLowerCase();
    db.prepare(`INSERT INTO components (uuid, title, display_title, description, source, version, ticket, docType, dataStr, project_uuid, child_tag, parent_tag, custom_tags)
                VALUES (?, ?, ?, ?, '', '1.0', 1, 2, ?, ?, '', '', '')`)
      .run(cuuid, c.ref, c.ref, c.type, JSON.stringify(c), project_uuid);
  });

  console.log('[OK] .eprj2 reconstructed');
  db.close();
}

main();