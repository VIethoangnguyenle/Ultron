import json
import os
import shutil
from datetime import datetime

TARGET_DIR = "/home/zane/Desktop/work/vietbank/vietbank-digital/.ua"
TARGET_GRAPH = os.path.join(TARGET_DIR, "knowledge-graph.json")
BACKUP_GRAPH = os.path.join(TARGET_DIR, "knowledge-graph.skeleton-backup.json")
TARGET_META = os.path.join(TARGET_DIR, "meta.json")
REPORT_FILE = os.path.join(TARGET_DIR, "merge-report.md")

SOURCES = [
    {
        "path": "/home/zane/Desktop/work/vietbank/vietbank-digital/vietbank-omni/.ua/knowledge-graph.json",
        "prefix": "vietbank-omni/"
    },
    {
        "path": "/home/zane/Desktop/work/vietbank/vietbank-digital/viet-bank-omni-ekyc/.ua/knowledge-graph.json",
        "prefix": "viet-bank-omni-ekyc/"
    },
    {
        "path": "/home/zane/Desktop/work/dvnh-common/.understand-anything/knowledge-graph.json",
        "prefix": "dvnh-common/"
    }
]

def update_id(old_id, prefix):
    parts = old_id.split(':', 1)
    if len(parts) == 2:
        type_str, rest = parts
        if type_str not in ("layer", "domain", "flow"):
            return f"{type_str}:{prefix}{rest}"
    return old_id

def process_graph(graph_data, prefix):
    # Prefix nodes
    for node in graph_data.get('nodes', []):
        node['id'] = update_id(node.get('id', ''), prefix)
        if 'filePath' in node:
            node['filePath'] = prefix + node['filePath']

    # Prefix edges
    for edge in graph_data.get('edges', []):
        for key in ('source', 'target', 'sourceId', 'targetId'):
            if key in edge:
                edge[key] = update_id(edge[key], prefix)

    # Prefix tour
    for tour_item in graph_data.get('tour', []):
        if 'nodeIds' in tour_item:
            tour_item['nodeIds'] = [update_id(nid, prefix) for nid in tour_item['nodeIds']]

    # Prefix layers, domains, flows
    for col in ('layers', 'domains', 'flows'):
        for item in graph_data.get(col, []):
            if 'nodeIds' in item:
                item['nodeIds'] = [update_id(nid, prefix) for nid in item['nodeIds']]

def main():
    print("Bắt đầu merge knowledge graph...")
    
    # 1. Backup
    if os.path.exists(TARGET_GRAPH) and not os.path.exists(BACKUP_GRAPH):
        shutil.copy2(TARGET_GRAPH, BACKUP_GRAPH)
        print(f"Đã backup: {BACKUP_GRAPH}")

    merged_nodes = {}
    merged_edges = {}
    merged_layers = {}
    merged_domains = {}
    merged_flows = {}
    merged_tour = []
    
    total_original_nodes = 0
    report_details = []

    for src in SOURCES:
        with open(src['path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        orig_node_count = len(data.get('nodes', []))
        orig_edge_count = len(data.get('edges', []))
        total_original_nodes += orig_node_count
        
        report_details.append({
            "name": src['prefix'].strip('/'),
            "nodes": orig_node_count,
            "edges": orig_edge_count
        })

        process_graph(data, src['prefix'])

        for node in data.get('nodes', []):
            merged_nodes[node['id']] = node

        for edge in data.get('edges', []):
            src_id = edge.get('source') or edge.get('sourceId')
            tgt_id = edge.get('target') or edge.get('targetId')
            edge_type = edge.get('type', '')
            key = f"{src_id}|{tgt_id}|{edge_type}"
            merged_edges[key] = edge

        for layer in data.get('layers', []):
            lid = layer['id']
            if lid not in merged_layers:
                merged_layers[lid] = layer
            else:
                merged_layers[lid]['nodeIds'] = list(set(merged_layers[lid].get('nodeIds', []) + layer.get('nodeIds', [])))

        for domain in data.get('domains', []):
            did = domain['id']
            if did not in merged_domains:
                merged_domains[did] = domain
            else:
                merged_domains[did]['nodeIds'] = list(set(merged_domains[did].get('nodeIds', []) + domain.get('nodeIds', [])))

        for flow in data.get('flows', []):
            fid = flow['id']
            if fid not in merged_flows:
                merged_flows[fid] = flow
            else:
                merged_flows[fid]['nodeIds'] = list(set(merged_flows[fid].get('nodeIds', []) + flow.get('nodeIds', [])))

        merged_tour.extend(data.get('tour', []))

    final_nodes = list(merged_nodes.values())
    final_edges = list(merged_edges.values())
    
    duplicates_removed = total_original_nodes - len(final_nodes)
    
    # Validate
    orphan_edges = []
    for edge in final_edges:
        src_id = edge.get('source') or edge.get('sourceId')
        tgt_id = edge.get('target') or edge.get('targetId')
        if src_id not in merged_nodes or tgt_id not in merged_nodes:
            orphan_edges.append(edge)

    if orphan_edges:
        print(f"VALIDATE FAIL: Found {len(orphan_edges)} orphan edges. Không ghi đè.")
        print(f"Ví dụ orphan edge: {orphan_edges[0]}")
        return

    print("VALIDATE PASS: Không có orphan edges, Node count hợp lệ.")

    # Read base project from skeleton if exists
    project_data = {}
    version = "1.0.0"
    if os.path.exists(BACKUP_GRAPH):
        with open(BACKUP_GRAPH, 'r', encoding='utf-8') as f:
            skel = json.load(f)
            project_data = skel.get('project', {})
            version = skel.get('version', "1.0.0")

    final_graph = {
        "version": version,
        "project": project_data,
        "nodes": final_nodes,
        "edges": final_edges,
        "tour": merged_tour,
        "layers": list(merged_layers.values()),
        "domains": list(merged_domains.values()),
        "flows": list(merged_flows.values())
    }
    
    # Remove empty lists to keep it clean
    for k in ["tour", "layers", "domains", "flows"]:
        if not final_graph[k]:
            del final_graph[k]

    try:
        json_str = json.dumps(final_graph, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"VALIDATE FAIL: Lỗi JSON encode: {e}")
        return

    # Write
    with open(TARGET_GRAPH, 'w', encoding='utf-8') as f:
        f.write(json_str)

    # Update meta.json
    now_str = datetime.utcnow().isoformat() + "Z"
    if os.path.exists(TARGET_META):
        with open(TARGET_META, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    else:
        meta = {}
    
    meta['analyzedFiles'] = len(final_nodes)
    meta['lastAnalyzedAt'] = now_str
    meta['mergedFrom'] = [s['prefix'].strip('/') for s in SOURCES]

    with open(TARGET_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    # Generate Report
    report_content = f"# Báo cáo Gộp Knowledge Graph\n\n"
    report_content += f"- **Thời điểm gộp**: {now_str}\n"
    report_content += f"- **Tổng số node cuối cùng**: {len(final_nodes)}\n"
    report_content += f"- **Tổng số cạnh cuối cùng**: {len(final_edges)}\n"
    report_content += f"- **Số node bị loại bỏ do trùng lặp**: {duplicates_removed}\n"
    report_content += f"- **Số cạnh orphan**: 0 (Đã pass validate)\n\n"
    report_content += "## Chi tiết từng nguồn\n"
    for d in report_details:
        report_content += f"- **{d['name']}**: {d['nodes']} node, {d['edges']} cạnh\n"

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"Hoàn thành! Ghi {len(final_nodes)} node và {len(final_edges)} edge.")

if __name__ == '__main__':
    main()
