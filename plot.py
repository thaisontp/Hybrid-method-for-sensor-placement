import matplotlib.pyplot as plt

def parse_inp(file_path):
    sections = {}
    current_section = None
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Bỏ qua dòng trống hoặc chú thích
            if not line or line.startswith(';'):
                continue
            
            # Kiểm tra tiêu đề Section
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1].upper()
                sections[current_section] = []
                continue
            
            if current_section:
                sections[current_section].append(line)
    return sections

# Đường dẫn file
file_path = 'Net3.inp'
sections = parse_inp(file_path)

# 1. Trích xuất tọa độ (COORDINATES)
coords = {}
if 'COORDINATES' in sections:
    for line in sections['COORDINATES']:
        parts = line.split()
        if len(parts) >= 3:
            coords[parts[0]] = (float(parts[1]), float(parts[2]))

# 2. Trích xuất danh sách đường ống (PIPES)
pipes = []
if 'PIPES' in sections:
    for line in sections['PIPES']:
        parts = line.split()
        if len(parts) >= 3:
            pipes.append({'id': parts[0], 'n1': parts[1], 'n2': parts[2]})

# Bổ sung Pumps và Valves nếu chúng được coi là các đoạn nối
for sec_name in ['PUMPS', 'VALVES']:
    if sec_name in sections:
        for line in sections[sec_name]:
            parts = line.split()
            if len(parts) >= 3:
                pipes.append({'id': parts[0], 'n1': parts[1], 'n2': parts[2]})

# Danh sách ID cần làm nổi bật
highlight_ids = ['113', '163', '191', '249', '295']
highlight_nodes = set()

plt.figure(figsize=(12, 10))

# Vẽ toàn bộ mạng lưới (màu đen nhạt)
for p in pipes:
    if p['n1'] in coords and p['n2'] in coords:
        x = [coords[p['n1']][0], coords[p['n2']][0]]
        y = [coords[p['n1']][1], coords[p['n2']][1]]
        if p['id'] not in highlight_ids:
            plt.plot(x, y, color='black', linewidth=0.8, alpha=0.4)

# Vẽ các đường ống mục tiêu (màu xanh dương nhạt)
for p in pipes:
    if p['id'] in highlight_ids:
        if p['n1'] in coords and p['n2'] in coords:
            x = [coords[p['n1']][0], coords[p['n2']][0]]
            y = [coords[p['n1']][1], coords[p['n2']][1]]
            plt.plot(x, y, color='skyblue', linewidth=3, zorder=5)
            highlight_nodes.add(p['n1'])
            highlight_nodes.add(p['n2'])

# Vẽ tất cả các nút (điểm đen nhỏ)
all_nodes_x = [c[0] for c in coords.values()]
all_nodes_y = [c[1] for c in coords.values()]
plt.scatter(all_nodes_x, all_nodes_y, color='black', s=5, zorder=3)

# Đánh số các Junction ở hai đầu ống được highlight
for node_id in highlight_nodes:
    if node_id in coords:
        plt.text(coords[node_id][0], coords[node_id][1], node_id, 
                 fontsize=11, fontweight='bold', color='blue',
                 ha='right', va='bottom', zorder=10)


plt.title('Net 3 Network with Highlighted Pipes')
plt.axis('equal')
plt.grid(True, linestyle='--', alpha=0.5)

# Lưu và hiển thị
plt.savefig('net3_plot.png', dpi=300)
plt.show()