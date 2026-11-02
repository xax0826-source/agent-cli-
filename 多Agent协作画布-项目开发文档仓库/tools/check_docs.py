#!/usr/bin/env python3
"""Check development-doc repository invariants without third-party Python modules.

Usage: python3 tools/check_docs.py [--root PATH]
Full Mermaid parsing is optional and requires `mmdc` in PATH; otherwise checks are structural.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

EXPECTED_COLS = (
    '任务编号', '拆分后的任务目标', '关联流程图节点／下层开发入口',
    '文件文档继续入口', '前置依赖／阻塞原因', '验收标准', '完成状态',
)
VALID_STATES = ('待开始', '进行中', '受阻', '待验收', '已完成', '已废弃')


def lines_as_cols(line: str) -> list[str]:
    # Ignore escaped vertical bars when splitting the Markdown task table.
    trimmed = line.strip()
    if not (trimmed.startswith('|') and trimmed.endswith('|')):
        return []
    return [c.strip() for c in re.split(r'(?<!\\)\|', trimmed[1:-1])]


def section(text: str, needle: str) -> str | None:
    match = re.search(r'^##\s+(\d+)\.\s+' + re.escape(needle) + r'\s*$', text, re.M)
    if not match:
        return None
    after = text[match.end():]
    end = re.search(r'^##\s+', after, re.M)
    return after[:end.start()] if end else after


def table_rows(sec: str) -> list[list[str]]:
    return [lines_as_cols(line) for line in sec.splitlines() if line.strip().startswith('|')]


def check(root: Path) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    info: list[str] = []
    mds = sorted(root.rglob('*.md'))
    mmds = sorted(root.rglob('*.mmd'))
    all_graph_ids: dict[tuple[str, str], Path] = {}
    node_ids: dict[str, Path] = {}
    displays: dict[Path, int] = {}
    total_links = 0
    all_tasks: dict[Path, dict[str, set[str]]] = {}

    def error(path: Path, msg: str) -> None:
        problems.append(f'{path.relative_to(root)}: {msg}')

    for md in mds:
        content = md.read_text(encoding='utf-8')
        # Links are validated against local file and explicit <a id> anchors.
        for raw in re.findall(r'\[[^\]]+\]\(([^)]+)\)', content):
            if raw.startswith(('http://', 'https://', 'mailto:')):
                continue
            dest, _, frag = raw.partition('#')
            if not dest and frag:
                target = md
            elif dest:
                target = (md.parent / unquote(dest)).resolve()
            else:
                continue
            total_links += 1
            if not target.is_file():
                error(md, f'本地链接不存在: {raw}')
                continue
            if frag and target.suffix.lower() == '.md':
                target_text = target.read_text(encoding='utf-8')
                anchors = set(re.findall(r'<a\s+id="([^"]+)"', target_text))
                # All formal task/continue links are explicit anchors; allow heading slugs.
                heads = [s.strip().lower() for s in re.findall(r'^#{1,6}\s+(.+)$', target_text, re.M)]
                if frag not in anchors and not any(frag == re.sub(r'[^\w\u4e00-\u9fff-]', '', h.replace(' ', '-')) for h in heads):
                    error(md, f'章节锚点不存在: {raw}')

        for match in re.finditer(r'<!-- diagram-source: ([^\n]+) -->\s*```mermaid\n(.*?)\n```', content, re.S):
            raw_source = match.group(1).strip()
            graph = (md.parent / raw_source).resolve()
            if not graph.is_file():
                error(md, f'diagram-source 不存在: {raw_source}')
            else:
                displays[graph] = displays.get(graph, 0) + 1
                if match.group(2).rstrip('\r\n') != graph.read_text(encoding='utf-8').rstrip('\r\n'):
                    error(md, f'Mermaid 展示副本与图源不一致: {raw_source}')
        if '文件开发文档' in md.parts:
            # file docs use sections 1–8; no development task table required.
            if '## 8. 落盘更改记录' not in content or '## 7. 当前具体进度' not in content:
                error(md, '文件文档缺少当前进度或落盘更改记录')
            if 'tools/check_docs.py.md' not in str(md) and '拟新增代码文件' not in content:
                error(md, '未实现源码的文件文档未标注拟新增')
            continue
        if '## 当前进度与直接跳转' not in content:
            error(md, '缺少文首“当前进度与直接跳转”')
        effective, obsolete = section(content, '需完成任务序列'), section(content, '已执行但已废弃的任务序列')
        if effective is None or obsolete is None:
            error(md, '需同时包含有效任务表和文末废弃任务表')
            continue
        h2s = re.findall(r'^##\s+\d+\.\s+(.+?)\s*$', content, re.M)
        if not h2s or h2s[-1] != '已执行但已废弃的任务序列':
            error(md, '废弃任务表必须放在最后一个二级章节')
        states = {}
        local_dependencies: dict[str, set[str]] = {}
        for section_name, part in [('有效', effective), ('废弃', obsolete)]:
            rows = table_rows(part)
            if len(rows) < 2 or tuple(rows[0]) != EXPECTED_COLS or len(rows[1]) != 7 or any(c.strip('-: ') for c in rows[1]):
                error(md, f'{section_name}任务表缺少固定七列标题及分隔行')
                continue
            for ix, row in enumerate(rows[2:], start=1):
                if len(row) != 7:
                    error(md, f'{section_name}任务表第 {ix} 行的列数是 {len(row)}，应为 7')
                    continue
                task_match = re.search(r'<a id="task-(\d+)"></a>T-(\d+)', row[0])
                if not task_match or task_match.group(1) != task_match.group(2):
                    error(md, f'{section_name}任务表第 {ix} 行编号与锚点不匹配')
                    continue
                tid = 'T-' + task_match.group(2)
                if tid in states:
                    error(md, f'任务编号重复: {tid}')
                status = re.sub(r'<br>.*$', '', row[6]).replace('*','').strip()
                states[tid] = (status, section_name)
                if status not in VALID_STATES:
                    error(md, f'{tid} 状态不合法: {status}')
                if section_name == '有效':
                    if status == '已废弃':
                        error(md, f'{tid} 已废弃却仍在有效任务表')
                    local_dependencies[tid] = {'T-' + x for x in re.findall(r'\[T-(\d+)\]\(#task-\d+\)', row[4])}
                    if '前置依赖：' not in row[4] or '阻塞：' not in row[4]:
                        error(md, f'{tid} 依赖／阻塞两项必填')
                    if not all(row[j] for j in (1,2,3,5)):
                        error(md, f'{tid} 有效任务缺少目标、关联节点、文件继续入口或验收标准')
                    if status == '已完成' and ('验收依据' not in row[6] or '](' not in row[6]):
                        error(md, f'{tid} 已完成但缺少文件文档验收依据链接')
                    if status == '受阻' and '解除条件：' not in row[4]:
                        error(md, f'{tid} 受阻但未写解除条件')
                else:
                    if status != '已废弃':
                        error(md, f'{tid} 废弃表行状态必须已废弃')
                    if not row[1].startswith('实际更改：') or row[2] != '—' or row[4] != '—' or row[5] != '—':
                        error(md, f'{tid} 废弃行仍含旧目标/依赖或缺少实际更改摘要')
            if section_name == '废弃' and len(rows) == 2 and '暂无已执行后废弃的任务' not in part:
                error(md, '空废弃任务表缺少“暂无”说明')
        all_tasks[md] = { 'effective': {k for k,(v,t) in states.items() if t=='有效'}, 'obsolete': {k for k,(v,t) in states.items() if t=='废弃'}}
        # same-document links checked above; progress must not refer to obsolete tasks.
        pos = content.find('## 当前进度与直接跳转')
        next_h = re.search(r'^##\s+', content[pos+5:], re.M)
        summary_block = content[pos:pos+5+next_h.start()] if next_h else content
        for task in all_tasks[md]['obsolete']:
            if '[' + task in summary_block:
                error(md, f'文首进度不允许引用废弃任务: {task}')
        for task in all_tasks[md]['effective']:
            if '[' + task not in summary_block:
                error(md, f'文首摘要没有有效任务入口: {task}')
        actual_progress: dict[str, str] = {}
        for category in ('已完成', '正在完成', '待完成'):
            item = re.search(r'^- ' + category + r'：(.+)$', summary_block, re.M)
            if not item:
                error(md, f'文首摘要缺少{category}项目')
                continue
            for number in re.findall(r'\[T-(\d+)', item.group(1)):
                task = 'T-' + number
                if task in actual_progress:
                    error(md, f'{task} 在文首摘要中重复归类')
                actual_progress[task] = category
        for task in all_tasks[md]['effective']:
            status = states[task][0]
            expected = '已完成' if status == '已完成' else ('正在完成' if status in ('进行中','待验收') else '待完成')
            if actual_progress.get(task) != expected:
                error(md, f'{task} 文首进度归类与任务状态不一致：应位于 {expected}')
        for task, dep_set in local_dependencies.items():
            for dependency in dep_set:
                if dependency in all_tasks[md]['obsolete']:
                    error(md, f'{task} 引用了已废弃的前置任务: {dependency}')
        visited, visiting = set(), set()
        def visit(task: str) -> None:
            if task in visiting:
                error(md, f'有效任务存在前置依赖循环，涉及 {task}')
                return
            if task in visited:
                return
            visiting.add(task)
            for dep in local_dependencies.get(task, set()):
                if dep in local_dependencies:
                    visit(dep)
            visiting.remove(task)
            visited.add(task)
        for task in local_dependencies:
            visit(task)

    for path in mmds:
        text = path.read_text(encoding='utf-8')
        graph_id = re.search(r'^%% diagram-id: ([\d.]+)$', text, re.M)
        view = re.search(r'^%% view: (current|target)$', text, re.M)
        if graph_id is None or view is None:
            error(path, '缺少合法的 diagram-id 或 view 注释')
        else:
            key = (graph_id.group(1), view.group(1))
            if key in all_graph_ids:
                error(path, f'图编号/view 冲突，首次见 {all_graph_ids[key].relative_to(root)}')
            all_graph_ids[key] = path
        if not re.search(r'^flowchart\s+(LR|RL|TB|TD|BT)\s*$', text, re.M):
            error(path, '缺少 flowchart 方向声明')
        if 'classDef pending' not in text:
            error(path, '缺少待实现的颜色与文字图例类')
        node_maps = re.findall(r'^%% node-doc: (N\d+(?:_\d+)*) = (.+)$', text, re.M)
        defined_nodes = re.findall(r'^\s*(N\d+(?:_\d+)*)\["(\d+(?:\.\d+)*) ([^\n"]+)"\]', text, re.M)
        mapping = {node: rel for node, rel in node_maps}
        if len(mapping) != len(node_maps):
            error(path, 'node-doc 映射存在重复节点 ID')
        if len(defined_nodes) != len(node_maps):
            error(path, f'图源定义了 {len(defined_nodes)} 个节点，但有 {len(node_maps)} 条 node-doc 映射')
        for node, label_no, label in defined_nodes:
            if node != 'N' + label_no.replace('.', '_'):
                error(path, f'{node} 与标签中的稳定编号 {label_no} 不匹配')
            if node not in mapping:
                error(path, f'{node} 没有 node-doc 注释')
            else:
                target = (path.parent / mapping[node]).resolve()
                if not target.is_file():
                    error(path, f'{node} 节点文档不存在: {mapping[node]}')
                if node in node_ids and node_ids[node] != path:
                    error(path, f'{node} 多处原始定义: {node_ids[node].relative_to(root)}')
                node_ids[node] = path
            if not any(s in label for s in ('待实现','进行中','部分实现','待验收','已实现·已验收')):
                error(path, f'{node} 缺少实现状态文字')
        if path not in displays:
            error(path, '没有主文档包含同步展示的 mermaid 代码块')

    # Optional full parser. It does not run in environments without mmdc.
    mmdc = shutil.which('mmdc')
    if mmdc:
        with tempfile.TemporaryDirectory() as tmp:
            for graph in mmds:
                rendered = Path(tmp) / (graph.stem + '.svg')
                result = subprocess.run([mmdc, '-i', str(graph), '-o', str(rendered)],capture_output=True,text=True)
                if result.returncode:
                    error(graph, f'mmdc 解析失败: {(result.stderr or result.stdout)[-350:]}')
        info.append('检测到 mmdc：已执行 Mermaid 完整渲染验证。')
    else:
        info.append('未安装 mmdc：仅执行 Mermaid 声明、映射、状态和展示副本的静态检查，未验证完整 Mermaid 解析。')
    info.append(f'扫描 {len(mds)} 份 Markdown、{len(mmds)} 份 .mmd；验证 {total_links} 条本地链接。')
    return problems, info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    errors, notes = check(root)
    for note in notes:
        print('[INFO] ' + note)
    for error in errors:
        print('[ERROR] ' + error)
    print('[PASS] 文档仓库静态检查通过。' if not errors else f'[FAIL] 检查发现 {len(errors)} 项问题。')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
