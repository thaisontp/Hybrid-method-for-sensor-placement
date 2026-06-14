"""
PHASE 1 — INPUT & PREPROCESS
- Input: Net3.inp (COORDINATES, JUNCTIONS, PIPES, PUMPS, RESERVOIRS, TANKS)
- Parse into NetworkData (dataframes + coordinates)
- Build pipe graph and save network plot (network_plot.png)

PHASE 2 — CLUSTERING (DMA)
- Build graph from PIPES and compute all-pairs shortest-path (Dijkstra) -> distance matrix
- Run HDBSCAN (metric='precomputed') with parameter search or defaults
- Optionally assign HDBSCAN noise to nearest cluster by pipe-distance
- Evaluate clusters (edge cut, modularity, demand balance, Todini RI)
- Export clustering plot and Top_Demand_Junctions_Clustering.csv

PHASE 3 — LEAK SCENARIOS & SIMULATION
- Create virtual leak node (276) by splitting a pipe and export leak_Cluster{X}.inp
- Generate demand scenarios (±20%) -> demand_scenarios.csv
- Run WNTR simulations per scenario × leak areas -> time-series leak datasets and pressure CSVs
- Save leak INP files and illustrative images

PHASE 4 — ENTROPY, SENSOR PLACEMENT & COVERAGE
- Aggregate time-series datasets and compute Shannon entropy per junction
- Rank nodes by entropy per DMA and select top‑N sensors
- Build sensitivity matrix (Sensor × Junction), apply noise threshold, compute coverage %
- Save results (Entropy_Sensor_Placement_Result.csv, Optimal_Sensors_Distribution.png, Sensor_Coverage_Map.png)

Inputs: Net3.inp, generated demand_scenarios.csv
Outputs: PNGs, CSVs, leak_Cluster*.inp, leak time-series datasets
"""
"""
========================================================================================================
Các file .csv
    demand_scenario.csv : Lưu 20% base demand
    Pressure_Cluster{x}.csv : Lưu áp suất cho từng kịch bản leak tại các Cluster khác nhau
    Top_Demand_Junctions_Clustering.csv: Lưu thông tin về top N junctions theo demand giảm dần sau khi đã phân cụm

=========================================================================================================
Các file .inp
    Net3.inp : Mô hình mạng lưới nước ban đầu
    leak_Cluster{x}.inp : Mô hình mạng lưới nước với kịch bản leak tại Cluster {x}
    leak_Cluster{x}_Timeseries_LeakArea_Dataset.csv : Lưu thông tin áp lực mô phỏng 

=========================================================================================================
Các biến quan trọng
    data_path = 'Net3.inp' : Đường dẫn đến file mô hình mạng lưới nước


Độ lọc nhiễu 0.001 
=========================================================================================================
### Phần 1: Lý thuyết nền tảng (The Theory)

Bài toán này được xây dựng trên 3 trụ cột lý thuyết chính:

**1. Lý thuyết Đồ thị (Graph Theory)**
Thay vì nhìn mạng lưới nước như một bản đồ CAD phức tạp, lý thuyết đồ thị trừu tượng hóa nó thành các **Đỉnh** (Nodes - là các điểm nối, bể chứa) và các **Cạnh** (Edges - là đường ống). Bằng cách này, máy tính có thể áp dụng các công thức toán học để phân tích cấu trúc của mạng lưới.

**2. Khoảng cách Tô-pô (Topological Distance) thay vì Không gian (Spatial)**

* **Sai lầm phổ biến:** Khi phân nhóm, người ta hay dùng khoảng cách "đường chim bay" (Euclidean distance) dựa trên tọa độ X, Y.
* **Thực tế mạng lưới nước:** Nước không bay qua không trung. Hai ngôi nhà có thể nằm sát vách nhau trên bản đồ, nhưng nếu đường ống phải đi vòng qua một con sông hoặc cao tốc, thì khoảng cách "thủy lực" của chúng là rất xa.
* **Cách giải quyết:** Đó là lý do code của bạn sử dụng thuật toán Dijkstra để tính khoảng cách dọc theo chiều dài ống thực tế. Những điểm "gần nhau" trong thuật toán này là những điểm mà nước có thể chảy qua lại một cách ngắn nhất.

**3. Phân cụm dựa trên mật độ (Density-based Clustering - HDBSCAN)**

* Thay vì chia đều mạng lưới thành các phần bằng nhau (như cắt bánh), **HDBSCAN** tìm kiếm các khu vực có "mật độ" cao.
* Nghĩa là: Những khu vực nào có nhiều nút kết nối với nhau bằng các đoạn ống ngắn chằng chịt (ví dụ: khu dân cư đông đúc), thuật toán sẽ gom chúng thành 1 cụm.
* Những nút nằm rải rác nối bằng các đường ống dài (như đường ống truyền tải ra ngoại ô) ban đầu sẽ bị coi là "nhiễu" (noise). Thuật toán của bạn sau đó có một bước thông minh là "kéo" các điểm nhiễu này về khu vực dân cư gần nhất.

---

### Phần 2: Ứng dụng thực tế (The Application)

Sản phẩm đầu ra của đoạn code này (các cụm cluster) đang giải quyết những bài toán trị giá hàng triệu đô la cho các công ty cấp nước đô thị.

**1. Thiết kế Phân vùng cấp nước độc lập (DMA - District Metered Area)**

* **Vấn đề:** Mạng lưới nước của một thành phố là một mạng lưới khổng lồ liên thông nhau. Nếu có thất thoát nước, bạn không thể biết nó đang xì ở quận nào.
* **Ứng dụng:** Code của bạn đang tự động hóa việc **chia mạng lưới khổng lồ đó thành các khu vực nhỏ (DMA)** (khoảng 500-3000 hộ dân). Mỗi cụm (cluster) chính là một DMA. Bằng cách đặt đồng hồ đo lưu lượng ở ranh giới giữa các DMA này, công ty cấp nước sẽ kiểm soát được lượng nước vào/ra của từng khu vực.

**2. Phát hiện và Định vị Rò rỉ (Leak Detection)**

* Đoạn code của bạn có phần tính toán `Entropy` từ dữ liệu cảm biến (`leak_path = 'DMA9.csv'`).
* **Ứng dụng:** Khi đã chia thành các DMA, việc tìm rò rỉ trở nên dễ dàng. Lý thuyết Entropy ở đây được dùng để đánh giá "sự hỗn loạn" hoặc độ bất thường của dữ liệu áp suất/lưu lượng. Điểm (Junction) nào có điểm số Entropy cao trong một cụm DMA, điểm đó có khả năng cao là vị trí đang bị rò rỉ hoặc xì vỡ ống.

**3. Tối ưu hóa & Quản lý Áp suất (Pressure Management)**

* Các khu vực có độ cao (Elevation) khác nhau cần áp suất khác nhau. Đẩy áp suất quá cao gây vỡ ống, quá thấp thì nước không lên được tầng lầu.
* **Ứng dụng:** Việc gom cụm các nút có đặc điểm địa hình và thủy lực gần nhau giúp kỹ sư biết chính xác vị trí nên đặt Van giảm áp (PRV) ở ranh giới các cụm, giúp giảm áp suất dư thừa, kéo dài tuổi thọ đường ống.

**4. Cô lập xử lý sự cố (Contamination & Maintenance)**

* **Ứng dụng:** Giả sử có một hóa chất độc hại lẫn vào mạng lưới, hoặc cần cắt nước để sửa chữa một đường ống cái. Nhờ cấu trúc chia cụm DMA, người vận hành chỉ cần đóng một số ít các van ở ranh giới cụm đó để **cô lập hoàn toàn khu vực bị ảnh hưởng**, mà không làm mất nước của cả thành phố.

Tóm lại, thuật toán mà bạn đang chạy không chỉ là một bài toán lập trình đơn thuần; nó là công cụ mô phỏng để các kỹ sư thiết kế lại cách vận hành mạng lưới nước của một thành phố thông minh hơn, tiết kiệm nước hơn và an toàn hơn.

"""


# =======================================================================================================
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
import networkx as nx
import argparse
from sklearn.cluster import HDBSCAN
from sklearn.metrics import silhouette_score
import math
from collections import defaultdict
import wntr
import os
import json
from matplotlib.colors import to_hex
import copy
import time
from ast import main
import pickle
import glob
from tqdm import tqdm

# Import thêm thư viện đánh giá chuyên biệt của hdbscan
try:
    from hdbscan.validity import validity_index
except ImportError:
    validity_index = None

# ========================================================
# ==================== BIẾN TOÀN CỤC =====================
# biến cho phase 1
data_path = 'Net3.inp'
data_image = 'network_plot.png'


# biến cho phase 2
# các biến cho HDBSCAN
TARGET_N_CLUSTERS = 10  # Nếu None, sẽ tự động chọn tham số min_cluster_size và min_samples tốt nhất dựa trên đánh giá chất lượng cluster
FORCE_ASSIGN_NOISE = True

# Tham so thu cong khi TARGET_N_CLUSTERS = None
MIN_CLUSTER_SIZE = 12
MIN_SAMPLES = 3

# Khoang tham so dung khi TARGET_N_CLUSTERS khac None
MIN_CLUSTER_SIZE_CANDIDATES = range(2, 31)
MIN_SAMPLES_CANDIDATES = range(1, 8)

# biến chọn số lượng top demand sẽ xuất lên console
top_n_value = 3

# biến chọn số lượng top demand sẽ xuất lên plot
top_demand_plot = 1

# các biến dùng cho phase 3
data_path = 'Net3.inp'
save_file = 'demand_scenarios.csv'
demand_csv = 'demand_scenarios.csv'

leak_node_id = '276'  
leak_areas = [0.001, 0.005, 0.01, 0.02, 0.05] 
discharge_coeff = 0.75

# Chọn số lượng top entropy junction (vị trí đặt sensor) sẽ xuất lên plot cho mỗi Cluster
TOP_ENTROPY_PLOT = 2

# ===================================================================================================
# ======================================= CODE PHASE 1 ==============================================
@dataclass
class NetworkData:
    """Cấu trúc dữ liệu mạng lưới nước"""
    junctions: pd.DataFrame      # ID, Elevation, Demand, Pattern
    pipes: pd.DataFrame          # ID, Node1, Node2, Length, Diameter, Status
    coordinates: Dict[str, Tuple[float, float]]  # Node ID -> (X, Y)
    pumps: pd.DataFrame          # ID, Node1, Node2
    reservoirs: pd.DataFrame     # ID, Head, Pattern
    tanks: pd.DataFrame          # ID, Elevation, InitLevel, etc.

class InpParser:
    """Parser cho file .inp (EPANET format)"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lines = []
        self._read_file()
    
    def _read_file(self):
        """Đọc file .inp"""
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            self.lines = f.readlines()
    
    def parse(self) -> NetworkData:
        """Parse toàn bộ file .inp và trả về NetworkData"""
        coords = self._parse_coordinates()
        junctions = self._parse_junctions()
        pipes = self._parse_pipes()
        pumps = self._parse_pumps()
        reservoirs = self._parse_reservoirs()
        tanks = self._parse_tanks()
        
        return NetworkData(
            junctions=junctions,
            pipes=pipes,
            coordinates=coords,
            pumps=pumps,
            reservoirs=reservoirs,
            tanks=tanks
        )
    
    def _find_section(self, section_name: str) -> Tuple[int, int]:
        """Tìm vị trí bắt đầu và kết thúc của một section"""
        section_name = f"[{section_name.upper()}]"
        start_idx = -1
        end_idx = len(self.lines)
        
        for i, line in enumerate(self.lines):
            if line.strip().upper() == section_name:
                start_idx = i
            elif start_idx != -1 and line.strip().startswith("["):
                end_idx = i
                break
        
        return start_idx, end_idx

    @staticmethod
    def _data_part(line: str) -> str:
        """Return the data before any EPANET inline comment."""
        return line.split(";", 1)[0].strip()
    
    def _parse_coordinates(self) -> Dict[str, Tuple[float, float]]:
        """Tích xuất tọa độ (X, Y) của các node"""
        start, end = self._find_section("COORDINATES")
        coords = {}
        
        if start == -1:
            return coords
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    node_id = parts[0]
                    x = float(parts[1])
                    y = float(parts[2])
                    coords[node_id] = (x, y)
                except (ValueError, IndexError):
                    continue
        
        return coords
    
    def _parse_junctions(self) -> pd.DataFrame:
        """Tích xuất các nút (junctions): ID, Elevation, Demand, Pattern"""
        start, end = self._find_section("JUNCTIONS")
        junctions = []
        if start == -1:
            return pd.DataFrame(columns=['ID', 'Elevation', 'Demand', 'Pattern'])
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    junction_id = parts[0]
                    elevation = float(parts[1])
                    demand = float(parts[2]) if parts[2] else 0.0
                    pattern = parts[3] if len(parts) > 3 else None
                    
                    junctions.append({
                        'ID': junction_id,
                        'Elevation': elevation,
                        'Demand': demand,
                        'Pattern': pattern
                    })
                except (ValueError, IndexError):
                    continue
        
        return pd.DataFrame(junctions, columns=['ID', 'Elevation', 'Demand', 'Pattern'])
    
    def _parse_pipes(self) -> pd.DataFrame:
        """Tích xuất các ống dẫn (pipes): ID, Node1, Node2, Length, Diameter, Status"""
        start, end = self._find_section("PIPES")
        pipes = []
        if start == -1:
            return pd.DataFrame(columns=['ID', 'Node1', 'Node2', 'Length', 'Diameter', 'Roughness', 'Status'])
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 8:
                try:
                    pipe_id = parts[0]
                    node1 = parts[1]
                    node2 = parts[2]
                    length = float(parts[3])
                    diameter = float(parts[4])
                    roughness = float(parts[5])
                    status = parts[7].upper()  # Open, Closed, CV, etc.
                    
                    pipes.append({
                        'ID': pipe_id,
                        'Node1': node1,
                        'Node2': node2,
                        'Length': length,
                        'Diameter': diameter,
                        'Roughness': roughness,
                        'Status': status
                    })
                except (ValueError, IndexError):
                    continue
        
        return pd.DataFrame(pipes, columns=['ID', 'Node1', 'Node2', 'Length', 'Diameter', 'Roughness', 'Status'])
    
    def _parse_pumps(self) -> pd.DataFrame:
        """Tích xuất các trạm bơm (pumps): ID, Node1, Node2, Parameters"""
        start, end = self._find_section("PUMPS")
        pumps = []
        if start == -1:
            return pd.DataFrame(columns=['ID', 'Node1', 'Node2', 'Parameters'])
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    pump_id = parts[0]
                    node1 = parts[1]
                    node2 = parts[2]
                    params = ' '.join(parts[3:]) if len(parts) > 3 else ''
                    
                    pumps.append({
                        'ID': pump_id,
                        'Node1': node1,
                        'Node2': node2,
                        'Parameters': params
                    })
                except (ValueError, IndexError):
                    continue
        
        return pd.DataFrame(pumps, columns=['ID', 'Node1', 'Node2', 'Parameters'])
    
    def _parse_reservoirs(self) -> pd.DataFrame:
        """Tích xuất các bể chứa (reservoirs): ID, Head, Pattern"""
        start, end = self._find_section("RESERVOIRS")
        reservoirs = []
        if start == -1:
            return pd.DataFrame(columns=['ID', 'Head', 'Pattern'])
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                try:
                    reservoir_id = parts[0]
                    head = float(parts[1])
                    pattern = parts[2] if len(parts) > 2 else None
                    
                    reservoirs.append({
                        'ID': reservoir_id,
                        'Head': head,
                        'Pattern': pattern
                    })
                except (ValueError, IndexError):
                    continue
        
        return pd.DataFrame(reservoirs, columns=['ID', 'Head', 'Pattern'])
    
    def _parse_tanks(self) -> pd.DataFrame:
        """Tích xuất các bể nước (tanks): ID, Elevation, InitLevel, MinLevel, MaxLevel"""
        start, end = self._find_section("TANKS")
        tanks = []
        if start == -1:
            return pd.DataFrame(columns=['ID', 'Elevation', 'InitLevel', 'MinLevel', 'MaxLevel', 'Diameter'])
        
        for line in self.lines[start+1:end]:
            line = self._data_part(line)
            if not line or line.startswith(";"):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                try:
                    tank_id = parts[0]
                    elevation = float(parts[1])
                    init_level = float(parts[2])
                    min_level = float(parts[3]) if len(parts) > 3 else 0.0
                    max_level = float(parts[4]) if len(parts) > 4 else 0.0
                    diameter = float(parts[5]) if len(parts) > 5 else 0.0
                    
                    tanks.append({
                        'ID': tank_id,
                        'Elevation': elevation,
                        'InitLevel': init_level,
                        'MinLevel': min_level,
                        'MaxLevel': max_level,
                        'Diameter': diameter
                    })
                except (ValueError, IndexError):
                    continue
        
        return pd.DataFrame(tanks, columns=['ID', 'Elevation', 'InitLevel', 'MinLevel', 'MaxLevel', 'Diameter'])

# Vẽ mạng lưới nước với các loại nút khác nhau
def plot_network_data(network_data: NetworkData, show_labels: bool = False) -> None:
    """Vẽ mạng lưới nước với các loại nút khác nhau."""
    coords = network_data.coordinates

    def node_positions(node_ids):
        xs, ys = [], []
        for node_id in node_ids:
            if node_id in coords:
                x, y = coords[node_id]
                xs.append(x)
                ys.append(y)
        return xs, ys

    plt.figure(figsize=(12, 10))

    # Vẽ đường ống
    if not network_data.pipes.empty:
        for _, pipe in network_data.pipes.iterrows():
            n1, n2 = pipe['Node1'], pipe['Node2']
            if n1 in coords and n2 in coords:
                x1, y1 = coords[n1]
                x2, y2 = coords[n2]
                is_open = pipe['Status'].upper() in ['OPEN', 'CV']
                plt.plot(
                    [x1, x2],
                    [y1, y2],
                    color='gray' if is_open else 'red',
                    linewidth=1,
                    linestyle='-' if is_open else '--',
                    alpha=0.6 if is_open else 0.8
                )

    # Vẽ junctions
    if not network_data.junctions.empty:
        junction_ids = network_data.junctions['ID'].tolist()
        xj, yj = node_positions(junction_ids)
        plt.scatter(xj, yj, marker='o', color='black', s=15, label='Junctions')

    # Vẽ tanks
    if not network_data.tanks.empty:
        tank_ids = network_data.tanks['ID'].tolist()
        xt, yt = node_positions(tank_ids)
        plt.scatter(xt, yt, marker='s', color='blue', s=50, edgecolors='white', linewidths=0.8, label='Tanks')

    # Vẽ reservoirs
    if not network_data.reservoirs.empty:
        reservoir_ids = network_data.reservoirs['ID'].tolist()
        xr, yr = node_positions(reservoir_ids)
        plt.scatter(xr, yr, marker='d', color='green', s=50, edgecolors='white', linewidths=0.8, label='Reservoirs')

    # Vẽ pumps
    if not network_data.pumps.empty:
        pump_xs, pump_ys = [], []
        for _, pump in network_data.pumps.iterrows():
            n1, n2 = pump['Node1'], pump['Node2']
            if n1 in coords and n2 in coords:
                x1, y1 = coords[n1]
                x2, y2 = coords[n2]
                plt.plot([x1, x2], [y1, y2], color='purple', linewidth=1.6, alpha=0.8)
                pump_xs.append((x1 + x2) / 2)
                pump_ys.append((y1 + y2) / 2)
        if pump_xs:
            plt.scatter(pump_xs, pump_ys, marker='h', color='purple', s=70,
                        edgecolors='yellow', linewidths=1, label='Pumps')

    plt.title('Water Network Plot')
    plt.xlabel('X coordinate')
    plt.ylabel('Y coordinate')
    plt.axis('equal')
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.legend()

    if show_labels:
        for node_id, (x, y) in coords.items():
            plt.text(x, y, node_id, fontsize=8, ha='right', va='bottom')

    plt.tight_layout()

# ========================================================
# ==================== CHẠY CODE 1 =======================
print("="*50)
print(f"PHASE 1: ĐỌC DỮ LIỆU VÀ TRỰC QUAN HÓA MẠNG LƯỚI NƯỚC f:{data_path}")
print("="*50)

print("\n1. Reading " + data_path + "...")
parser = InpParser(data_path)
network = parser.parse()

print("2. Plotting network...")
plot_network_data(network, show_labels=False)
plt.savefig(data_image, dpi=300)
print(f"-> Network plot saved to {data_image}")


# ===================================================================================================
# ======================================= CODE PHASE 2 ==============================================
def get_network_graph_data(network: NetworkData) -> Tuple[List[str], np.ndarray, Dict]:
    """
    Chuyển đổi NetworkData thành dữ liệu có thể dùng cho HDBSCAN
    
    Returns:
        nodes: Danh sách node IDs
        feature_matrix: Ma trận đặc trưng (X, Y, Elevation, Demand)
        graph_info: Thông tin kết nối đồ thị
    """
    
    # Danh sách tất cả các nút
    all_nodes = set()
    
    # Từ junctions
    if not network.junctions.empty:
        all_nodes.update(network.junctions['ID'].values)
    
    # Từ reservoirs
    if not network.reservoirs.empty:
        all_nodes.update(network.reservoirs['ID'].values)
    
    # Từ tanks
    if not network.tanks.empty:
        all_nodes.update(network.tanks['ID'].values)
    
    # Từ pipes
    if not network.pipes.empty:
        all_nodes.update(network.pipes['Node1'].values)
        all_nodes.update(network.pipes['Node2'].values)
    
    all_nodes = sorted(list(all_nodes))
    
    # Xây dựng ma trận đặc trưng
    features = []
    node_info = {}
    
    for node_id in all_nodes:
        x, y = network.coordinates.get(node_id, (0.0, 0.0))
        
        # Lấy thông tin từ junctions
        elevation = 0.0
        demand = 0.0
        
        if not network.junctions.empty:
            junction = network.junctions[network.junctions['ID'] == node_id]
            if not junction.empty:
                elevation = junction['Elevation'].values[0]
                demand = junction['Demand'].values[0]
        
        features.append([x, y, elevation, demand])
        node_info[node_id] = {
            'x': x, 'y': y, 'elevation': elevation, 'demand': demand
        }
    
    feature_matrix = np.array(features)
    
    # Thông tin kết nối
    graph_info = {
        'nodes': all_nodes,
        'edges': [],
        'pipe_edges': [],
        'pump_edges': [],
        'node_connections': {n: [] for n in all_nodes}
    }
    
    # Thêm edges từ pipes
    if not network.pipes.empty:
        for _, row in network.pipes.iterrows():
            if row['Status'].upper() in ['OPEN', 'CV']:
                node1, node2 = row['Node1'], row['Node2']
                graph_info['edges'].append((node1, node2, row['Length']))
                graph_info['pipe_edges'].append((node1, node2, row['Length']))
                if node1 in graph_info['node_connections']:
                    graph_info['node_connections'][node1].append(node2)
                if node2 in graph_info['node_connections']:
                    graph_info['node_connections'][node2].append(node1)
    
    # Thêm edges từ pumps
    if not network.pumps.empty:
        for _, row in network.pumps.iterrows():
            node1, node2 = row['Node1'], row['Node2']
            graph_info['edges'].append((node1, node2, 10.0))  # Virtual weight for pumps
            graph_info['pump_edges'].append((node1, node2, 10.0))
            if node1 in graph_info['node_connections']:
                graph_info['node_connections'][node1].append(node2)
            if node2 in graph_info['node_connections']:
                graph_info['node_connections'][node2].append(node1)
    
    return all_nodes, feature_matrix, graph_info, node_info

# ===================================================================================================
def get_top_demand_junctions(network: NetworkData, top_n: int = 5) -> pd.DataFrame:
    """Trả về top N junctions theo Demand giảm dần.

    Trả về DataFrame gồm các cột: ID, Demand, Elevation, X, Y
    """
    if network.junctions is None or network.junctions.empty:
        return pd.DataFrame(columns=['ID', 'Demand', 'Elevation', 'X', 'Y'])

    df = network.junctions.copy()
    # Đảm bảo cột Demand là số và không có NaN
    df['Demand'] = pd.to_numeric(df['Demand'], errors='coerce').fillna(0.0)

    # Gắn tọa độ nếu có
    coords = network.coordinates if network.coordinates is not None else {}
    df['X'] = df['ID'].map(lambda i: coords.get(i, (None, None))[0])
    df['Y'] = df['ID'].map(lambda i: coords.get(i, (None, None))[1])

    df_sorted = df.sort_values(by='Demand', ascending=False).head(top_n)
    return df_sorted[['ID', 'Demand', 'Elevation', 'X', 'Y']]

# ============================================================================================================================
"""
File INP chỉ chứa "Khoảng cách trực tiếp" (Direct Edges)
Dữ liệu trong phần [PIPES] của file .inp chỉ cho biết chiều dài của một đoạn ống nối trực tiếp giữa 2 điểm kề nhau (hàng xóm).

Vấn đề: Nếu Điểm A nối với Điểm B (dài 10m), và Điểm B nối với Điểm C (dài 20m). 
File INP chỉ ghi nhận (A-B: 10) và (B-C: 20). Nó không hề ghi nhận khoảng cách giữa A và C.

Nếu bê nguyên file INP vào ma trận, ô khoảng cách giữa A và C sẽ là khoảng trống (hoặc vô cực). 
Thuật toán phân cụm HDBSCAN sẽ hiểu nhầm rằng A và C cách nhau xa vô tận và không bao giờ xếp chúng vào chung một cụm DMA, 
dù thực tế chúng chỉ cách nhau 30m.

Ma trận khoảng cách yêu cầu "Khoảng cách giữa TẤT CẢ các điểm" (All-Pairs Distance)Ma trận Distance Matrix (n x n) 
yêu cầu bạn phải điền đầy đủ khoảng cách từ Mọi điểm -> Đến mọi điểm khác trong toàn bộ mạng lưới.
Để tính được khoảng cách từ điểm đầu làng đến điểm cuối làng (không có ống nối trực tiếp), 
code bắt buộc phải dùng thuật toán (Dijkstra) để cộng dồn chiều dài của tất cả các đoạn ống trung gian tạo nên tuyến đường đó.
"""

# ===========================================================================================================================
"""
Thuật toán Dijkstra của networkx
Thuật toán Dijkstra (phát minh bởi nhà khoa học máy tính Edsger W. Dijkstra năm 1956) 
là một trong những thuật toán kinh điển và thanh lịch nhất trong khoa học máy tính. 
Nó chuyên dùng để giải quyết bài toán: Tìm đường đi ngắn nhất từ một điểm xuất phát đến tất cả các điểm còn lại 
trong một đồ thị có trọng số không âm (chiều dài ống nước không thể là số âm, nên thuật toán này là lựa chọn hoàn hảo).

Dijkstra là một thuật toán mang tính "tham lam" (Greedy Algorithm). Nó luôn tin rằng: 
Đường đi ngắn nhất đến một điểm X bất kỳ phải đi qua một điểm Y lân cận mà ta đã biết chắc chắn là ngắn nhất
Nó giải quyết bài toán bằng cách đi từng bước cẩn thận, mở rộng dần vùng an toàn (những điểm đã tìm được khoảng cách ngắn nhất) ra xung quanh.

Thuật toán hoạt động như thế nào (Từng bước một)
Hãy tưởng tượng bạn đang đứng ở nút gốc (Nút A) và muốn tính khoảng cách ngắn nhất đến mọi nút khác. Thuật toán làm như sau:
    1.	Khởi tạo:
        Gán khoảng cách từ Nút A đến chính nó là 0.
        Gán khoảng cách từ Nút A đến tất cả các nút còn lại là infty (vô cực - chưa biết đường đi).
        Tạo một danh sách các "Nút chưa thăm" (ban đầu gồm tất cả các nút).
    2.	Chọn Nút để xét:
        Trong số các nút chưa thăm, chọn nút có khoảng cách nhỏ nhất hiện tại. (Ở bước đầu tiên, đó chính là Nút A với khoảng cách là 0).
    3.	Cập nhật hàng xóm:
        Từ nút đang xét, nhìn sang tất cả các "nút hàng xóm" (các nút nối trực tiếp bằng 1 đường ống).
        Tính khoảng cách dự kiến: Khoảng cách đến nút hiện tại + Chiều dài ống nối đến hàng xóm.
        Cốt lõi là đây: Nếu khoảng cách dự kiến này nhỏ hơn khoảng cách hiện đang được ghi chép của nút hàng xóm, thì cập nhật lại kỷ lục đó.
            Ví dụ: Khoảng cách hiện tại đang ghi nhận A đến C là infty. Nút hiện tại là A (0), khoảng cách A-C là 10. Ta cập nhật: A đến C là 10 (vì 0 + 10 < infty).
    4.	Đánh dấu Đã thăm:
        Khi đã xét xong tất cả hàng xóm của nút hiện tại, ta đánh dấu nút này là "Đã thăm" và loại nó khỏi danh sách chờ. Một khi đã đánh dấu, khoảng cách đến nút này được chốt cứng và không bao giờ thay đổi nữa.
    5.	Lặp lại:
        Quay lại Bước 2, tiếp tục chọn nút chưa thăm có khoảng cách nhỏ nhất tiếp theo để xét, cho đến khi không còn nút nào.

Cách thư viện networkx tối ưu (Under the hood)
Hàm nx.all_pairs_dijkstra_path_length trong Python không chỉ code chay thuật toán trên mà nó dùng cấu trúc dữ liệu rất xịn:
•	Min-Heap Priority Queue (Hàng đợi ưu tiên): Thay vì dùng vòng lặp dò tìm "nút nào có khoảng cách nhỏ nhất" một cách chậm chạp, 
    networkx dùng mô-đun heapq của Python. Nhờ đó, nó lấy ra nút gần nhất chỉ mất thời gian O(log V) thay vì O(V).
•	All-Pairs (Tất cả các cặp): Bản chất Dijkstra ban đầu chỉ tìm đường từ 1 điểm đến mọi điểm (Single-Source). 
    Khi bạn gọi all_pairs, thư viện networkx đơn giản là chạy một vòng lặp: nó đặt Dijkstra đứng tại Nút 1 và chạy, 
    xong nó sang Nút 2 đứng và chạy tiếp... cho đến khi chạy qua toàn bộ danh sách điểm.

Độ phức tạp tính toán (Time Complexity):
Với một đồ thị có V đỉnh (Junctions/Tanks) và E cạnh (Pipes), thời gian chạy Dijkstra cho 1 điểm là O{(E + V.log(V)}. Khi chạy cho toàn bộ mạng lưới (all_pairs), thời gian là O(V . (E + V log V)). 
Đây là lý do nếu mạng lưới nước của bạn quá lớn (hàng chục ngàn ống), bước này sẽ mất kha khá thời gian để tính toán.

"""
# ============================================================================================================
def count_clusters(labels) -> int:
    return len(set(labels) - {-1})

# ============================================================================================================
def build_cluster_pipe_graph(network_data):
    """
    Build a graph from pipes in {data_path}.

    Junctions and tanks are clustered. Reservoirs and other pipe endpoints may
    still exist in the graph as transit nodes for shortest paths.
    Pumps are intentionally excluded because this workflow uses [PIPES] only.
    """
    graph = nx.Graph()
    pipe_edges = []

    if not network_data.pipes.empty:
        for _, pipe in network_data.pipes.iterrows():
            status = str(pipe["Status"]).upper()
            if status not in ["OPEN", "CV"]:
                continue

            node1 = str(pipe["Node1"])
            node2 = str(pipe["Node2"])
            length = float(pipe["Length"])
            graph.add_edge(node1, node2, weight=length)
            pipe_edges.append((node1, node2, length))

    cluster_nodes = []
    node_info = {}
    features = []

    for _, junction in network_data.junctions.iterrows():
        node_id = str(junction["ID"])
        x, y = network_data.coordinates.get(node_id, (0.0, 0.0))
        elevation = float(junction["Elevation"])
        demand = float(junction["Demand"])

        node_info[node_id] = {
            "type": "Junction",
            "x": x,
            "y": y,
            "elevation": elevation,
            "demand": demand,
        }
        cluster_nodes.append(node_id)
        features.append([x, y, elevation, demand])

    if not network_data.tanks.empty:
        for _, tank in network_data.tanks.iterrows():
            node_id = str(tank["ID"])
            x, y = network_data.coordinates.get(node_id, (0.0, 0.0))
            elevation = float(tank["Elevation"])
            demand = 0.0

            node_info[node_id] = {
                "type": "Tank",
                "x": x,
                "y": y,
                "elevation": elevation,
                "demand": demand,
            }
            cluster_nodes.append(node_id)
            features.append([x, y, elevation, demand])

    cluster_nodes = sorted(cluster_nodes)

    graph_info = {
        "nodes": cluster_nodes,
        "edges": pipe_edges,
        "pipe_edges": pipe_edges,
        "pump_edges": [],
        "node_connections": {node: [] for node in cluster_nodes},
    }

    for node1, node2, _ in pipe_edges:
        if node1 in graph_info["node_connections"]:
            graph_info["node_connections"][node1].append(node2)
        if node2 in graph_info["node_connections"]:
            graph_info["node_connections"][node2].append(node1)

    features = np.array([[
        node_info[node]["x"],
        node_info[node]["y"],
        node_info[node]["elevation"],
        node_info[node]["demand"],
    ] for node in cluster_nodes])

    return graph, cluster_nodes, features, graph_info, node_info

def compute_pipe_distance_matrix(graph: nx.Graph, cluster_nodes: list) -> np.ndarray:
    """
    Compute shortest-path distances between cluster nodes using pipe length.
    """
    n = len(cluster_nodes)
    distance_matrix = np.full((n, n), np.inf)
    np.fill_diagonal(distance_matrix, 0.0)

    path_lengths = dict(nx.all_pairs_dijkstra_path_length(graph, weight="weight"))

    for i, node1 in enumerate(cluster_nodes):
        for j, node2 in enumerate(cluster_nodes):
            distance_matrix[i, j] = path_lengths.get(node1, {}).get(node2, np.inf)

    finite_distances = distance_matrix[np.isfinite(distance_matrix)]
    if finite_distances.size == 0:
        raise ValueError("No cluster-node pipe distance could be computed.")

    disconnected_penalty = max(float(finite_distances.max()) * 10.0, 1e6)
    distance_matrix[~np.isfinite(distance_matrix)] = disconnected_penalty

    return distance_matrix

def show_distance_matrix(inp_file_path="Net3.inp"):
    """
    Hàm đọc file INP, tính toán khoảng cách qua đường ống và in ma trận ra console.
    Chỉ cần gọi hàm này là chạy được.
    """
    print(f"\n1. Đang đọc dữ liệu từ file: {inp_file_path}...")
    parser = InpParser(inp_file_path)
    network_data = parser.parse()
    
    print("2. Đang xây dựng đồ thị đường ống...")
    # Lấy dữ liệu đồ thị và danh sách các nút
    graph, cluster_nodes, features, graph_info, node_info = build_cluster_pipe_graph(network_data)
    
    if not cluster_nodes:
        print("[LỖI] Không tìm thấy nút Junction/Tank nào để tính toán.")
        return None
        
    print("3. Đang chạy thuật toán Dijkstra để tính ma trận khoảng cách...")
    # Tính ma trận
    distance_matrix = compute_pipe_distance_matrix(graph, cluster_nodes)
    
    # In ra console
    print(f"\n" + "="*60)
    print(f"MA TRẬN KHOẢNG CÁCH ({len(cluster_nodes)} x {len(cluster_nodes)})")
    print("="*60)
    
    # Tùy chọn: Hiển thị đầy đủ không bị cắt bớt (bỏ dấu # nếu muốn in full)
    # pd.set_option('display.max_rows', None) 
    # pd.set_option('display.max_columns', None)
    # pd.set_option('display.width', 1000)
    
    df_matrix = pd.DataFrame(distance_matrix, index=cluster_nodes, columns=cluster_nodes)
    print(df_matrix)
    print("="*60 + "\n")
    
    return df_matrix
# ============== HDBSCAN CLUSTERING ============================
def run_hdbscan(distance_matrix, min_cluster_size, min_samples):
    clusterer = HDBSCAN(
        min_cluster_size = min_cluster_size,
        min_samples = min_samples,
        metric = "precomputed",
        allow_single_cluster = False,
        copy = True,
    )
    labels = clusterer.fit_predict(distance_matrix)
    return clusterer, labels

"""
distance_matrix 
    A square (n_samples, n_samples) matrix containing pairwise distances. 
        Since metric="precomputed", HDBSCAN expects distances rather than raw feature vectors. 
min_cluster_size 
    Minimum number of points required to form a cluster. 
    Larger values produce fewer, larger clusters. 
    Smaller values allow more fine-grained clusters. 
min_samples 
    Controls how conservative the clustering is. 
    Higher values classify more points as noise (-1). 
    Lower values make clustering more permissive. 
metric="precomputed" 
    Tells HDBSCAN not to compute distances itself. 
allow_single_cluster=False 
    Prevents HDBSCAN from returning one giant cluster containing all points. 
    If no meaningful cluster structure exists, more points may be labeled as noise. 
copy=True 
    Creates an internal copy of the distance matrix instead of modifying the original.

"""

def find_hdbscan_params_for_target(distance_matrix, target_n_clusters):
    """
    HDBSCAN has no n_clusters parameter. This searches a small parameter grid
    and keeps the result with cluster count closest to target_n_clusters.
    """
    best = None
    n_points = distance_matrix.shape[0]

    for min_cluster_size in MIN_CLUSTER_SIZE_CANDIDATES:
        if min_cluster_size > n_points:
            continue

        for min_samples in MIN_SAMPLES_CANDIDATES:
            clusterer, labels = run_hdbscan(distance_matrix, min_cluster_size, min_samples)
            n_clusters = count_clusters(labels)
            n_noise = list(labels).count(-1)
            score = (abs(n_clusters - target_n_clusters), n_noise, min_cluster_size, min_samples)

            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "clusterer": clusterer,
                    "labels": labels,
                    "min_cluster_size": min_cluster_size,
                    "min_samples": min_samples,
                    "n_clusters": n_clusters,
                    "n_noise": n_noise,
                }

    if best is None:
        raise ValueError("No valid HDBSCAN parameter set was found.")

    return best

def assign_noise_to_nearest_cluster(labels, distance_matrix):
    """
    Replace label -1 by the nearest existing cluster using pipe-distance matrix.
    A noise node is assigned to the cluster with the smallest mean distance.
    """
    labels = np.array(labels, copy=True)
    cluster_ids = sorted(set(labels) - {-1})
    if -1 not in labels or not cluster_ids:
        return labels

    for noise_idx in np.where(labels == -1)[0]:
        best_cluster = min(
            cluster_ids,
            key=lambda cluster_id: float(distance_matrix[noise_idx, labels == cluster_id].mean()),
        )
        labels[noise_idx] = best_cluster

    return labels

def perform_clustering(
    network_data,
    target_n_clusters=None,
    min_cluster_size=12,
    min_samples=3,
    force_assign_noise=True,
):
    """
    Run HDBSCAN on cluster nodes using the pipe shortest-path distance matrix.
    """
    graph, nodes, features, graph_info, node_info = build_cluster_pipe_graph(network_data)

    type_counts = pd.Series([node_info[node]["type"] for node in nodes]).value_counts().to_dict()
    print(f"Nodes for clustering: {len(nodes)} {type_counts}")
    print(f"Feature matrix shape: {features.shape}")
    print(f"Pipe edges from {data_path}: {len(graph_info['pipe_edges'])}")

    print("\nComputing node distance matrix from pipe lengths...")
    # Handle case with no cluster nodes gracefully
    if not nodes:
        print("No clusterable junction/tank nodes found. Skipping clustering.")
        empty_result = {
            "clusterer": None,
            "labels": np.array([], dtype=int),
            "raw_labels": np.array([], dtype=int),
            "node_cluster": {},
            "nodes": [],
            "features": np.array([]),
            "graph_info": graph_info,
            "node_info": node_info,
            "distance_matrix": np.array([[]]),
            "min_cluster_size": min_cluster_size,
            "min_samples": min_samples,
        }
        return empty_result

    distance_matrix = compute_pipe_distance_matrix(graph, nodes)

    if target_n_clusters is not None:
        print(f"\nSearching HDBSCAN params closest to {target_n_clusters} clusters...")
        best = find_hdbscan_params_for_target(distance_matrix, target_n_clusters)
        clusterer = best["clusterer"]
        labels = best["labels"]
        min_cluster_size = best["min_cluster_size"]
        min_samples = best["min_samples"]
        print(
            f"Selected min_cluster_size={min_cluster_size}, min_samples={min_samples} "
            f"-> {best['n_clusters']} clusters, {best['n_noise']} noise nodes"
        )
    else:
        print(f"\nRunning HDBSCAN (min_cluster_size={min_cluster_size}, min_samples={min_samples})...")
        clusterer, labels = run_hdbscan(distance_matrix, min_cluster_size, min_samples)

    raw_labels = np.array(labels, copy=True)
    raw_noise = list(raw_labels).count(-1)
    if force_assign_noise and raw_noise:
        labels = assign_noise_to_nearest_cluster(labels, distance_matrix)
        print(f"Assigned {raw_noise} HDBSCAN noise nodes to nearest Clustering by pipe distance.")

    node_cluster = dict(zip(nodes, labels))
    unique_labels = set(labels)
    n_clusters = count_clusters(labels)
    n_noise = list(labels).count(-1)

    print(f"\nDetected Clustering clusters: {n_clusters}")
    print(f"Noise/unassigned nodes: {n_noise}")

    print("\nClustering statistics:")
    print("-" * 50)
    for cluster_id in sorted(unique_labels):
        label = "Noise/Transit" if cluster_id == -1 else f"Clustering {cluster_id}"
        count = list(labels).count(cluster_id)
        print(f"  {label:20s}: {count:3d} nodes")

    return {
        "clusterer": clusterer,
        "labels": labels,
        "raw_labels": raw_labels,
        "node_cluster": node_cluster,
        "nodes": nodes,
        "features": features,
        "graph_info": graph_info,
        "node_info": node_info,
        "distance_matrix": distance_matrix,
        "min_cluster_size": min_cluster_size,
        "min_samples": min_samples,
    }

# ĐÁNH GIÁ CLUSTER
def analyze_cluster_quality(result: dict, inp_file: str = 'Net3.inp'):
    """
    Đánh giá chất lượng phân vùng Clustering dựa trên 4 tiêu chí cốt lõi:
    1. Edge Cut: Số lượng ống ranh giới bị cắt.
    2. Modularity: Tính mô-đun của đồ thị mạng lưới.
    3. Demand Balance: Độ đồng đều về nhu cầu tiêu thụ nước giữa các cụm.
    4. Resilience Index: Chỉ số phục hồi thủy lực mạng lưới (Todini Index).
    """
    print("\n ========= BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG PHÂN VÙNG =========")
    
    labels = np.array(result["labels"])
    unique_clusters = set(labels) - {-1}
    n_clusters = len(unique_clusters)
    
    if n_clusters < 2:
        print(" Không đủ số lượng cụm hợp lệ (>= 2) để tiến hành đánh giá.")
        return

    pipe_edges = result.get("graph_info", {}).get("pipe_edges", [])
    node_cluster = result.get("node_cluster", {})
    
    if not pipe_edges:
        print(" Không tìm thấy dữ liệu đường ống để đánh giá.")
        return

    # =======================================================
    # 1. EDGE CUT (Lát cắt biên - Số đường ống bị cắt)
    # =======================================================
    total_edges = len(pipe_edges)
    internal_edges = 0
    
    for u, v, w in pipe_edges:
        c_u = node_cluster.get(u, -2)
        c_v = node_cluster.get(v, -3)
        if c_u == c_v and c_u != -1:
            internal_edges += 1
            
    edge_cut = total_edges - internal_edges
    print(f"    Edge Cut         : {edge_cut:>7} ống (Số vị trí cần lắp van/đồng hồ ranh giới)")

    # =======================================================
    # 2. MODULARITY (Tính Mô-đun cấu trúc liên kết)
    # =======================================================
    G = nx.Graph()
    for u, v, w in pipe_edges:
        G.add_edge(u, v)
        
    communities = []
    for c in unique_clusters:
        c_nodes = {n for n in result["nodes"] if node_cluster.get(n) == c}
        communities.append(c_nodes)
        
    noise_nodes = {n for n in result["nodes"] if node_cluster.get(n) == -1}
    for nn in noise_nodes:
        communities.append({nn})
        
    G_nodes = set(G.nodes())
    for comm in communities:
        G_nodes -= comm
    for missing in G_nodes:
        communities.append({missing})

    try:
        mod_score = nx.community.modularity(G, communities)
        print(f"    Modularity       : {mod_score:>7.4f} (Mức > 0.3 là cấu trúc đồ thị chia rất tốt)")
    except Exception as e:
        print(f"    Modularity       : Lỗi tính toán ({e})")

    # =======================================================
    # 3. DEMAND BALANCE (Độ cân bằng nhu cầu tiêu thụ)
    # =======================================================
    cluster_demands = []
    for c in unique_clusters:
        c_nodes = [n for n in result["nodes"] if node_cluster.get(n) == c]
        c_demand = sum(result["node_info"].get(n, {}).get("demand", 0.0) for n in c_nodes)
        cluster_demands.append(c_demand)
        
    if cluster_demands:
        mean_d = np.mean(cluster_demands)
        std_d = np.std(cluster_demands)
        cv_d = (std_d / mean_d) if mean_d > 0 else 0
        
        print(f"    Demand Balance   : CV = {cv_d:.2f} (Hệ số biến thiên - Càng gần 0 càng đồng đều)")
        print(f"-> Demand trung bình : {mean_d:.2f} | Chênh lệch: {np.min(cluster_demands):.2f} - {np.max(cluster_demands):.2f}")

    # =======================================================
    # 4. RESILIENCE INDEX (Chỉ số phục hồi thủy lực - Todini Index)
    # =======================================================
    try:
        # Tải mô hình thủy lực WNTR từ file INP
        wn = wntr.network.WaterNetworkModel(data_path)
        
        # Chạy mô phỏng thủy lực
        sim = wntr.sim.EpanetSimulator(wn)
        sim_res = sim.run_sim()
        
        # Lấy kết quả áp suất, cột nước, lưu lượng từ mô phỏng
        head = sim_res.node['head']
        pressure = sim_res.node['pressure']
        demand = sim_res.node['demand']
        pump_flowrate = sim_res.link['flowrate'].loc[:, wn.pump_name_list]
        
        # Đánh giá chỉ số phục hồi Todini (áp suất tối thiểu yêu cầu P_req = 15m)
        # Nếu theo TCVN, bạn có thể chỉnh P_req thành 10m hoặc 20m tùy ý
        ri = wntr.metrics.todini_index(head, pressure, demand, pump_flowrate, wn, Pstar=15)
        
        # Lấy giá trị RI trung bình của toàn bộ thời gian chạy mô phỏng
        mean_ri = ri.mean()
        print(f"    Resilience Index : {mean_ri:>7.4f} (Chỉ số Todini - Đánh giá độ dôi dư năng lượng/áp suất)")
    except Exception as e:
        print(f"    Resilience Index : Bỏ qua do lỗi mô phỏng WNTR ({e})")

def visualize_clusters(result: dict, network_data, save_path=None):
    """
    Plot Clustering result over the pipe network.

    Pumps and reservoirs are shown as reference markers only. They are not part
    of the HDBSCAN labels or pipe-distance matrix.
    """
    coordinates = network_data.coordinates
    labels = result["labels"]
    nodes = result["nodes"]
    node_cluster = result["node_cluster"]
    node_info = result["node_info"]
    graph_info = result["graph_info"]

    plt.figure(figsize=(14, 12))

    print("\nDrawing pipe network...")
    for node1, node2, _ in graph_info["pipe_edges"]:
        if node1 in coordinates and node2 in coordinates:
            x1, y1 = coordinates[node1]
            x2, y2 = coordinates[node2]
            plt.plot([x1, x2], [y1, y2], color="gray", linewidth=1, alpha=0.6, zorder=1)

    unique_clusters = sorted(set(labels))
    cmap = plt.colormaps.get_cmap("tab20")
    color_map = {cluster: cmap(i % 20) for i, cluster in enumerate(unique_clusters)}

    print("Drawing Clustering nodes...")
    for cluster_id in unique_clusters:
        cluster_nodes = [node for node in nodes if node_cluster[node] == cluster_id]

        if cluster_id == -1:
            color = "black"
            label = "Noise/Transit"
            size = 40
            marker = "x"
        else:
            color = color_map[cluster_id]
            label = f"Clustering {cluster_id}"
            size = 60
            marker = "o"

        xs = [coordinates[node][0] for node in cluster_nodes if node in coordinates]
        ys = [coordinates[node][1] for node in cluster_nodes if node in coordinates]

        if xs:
            scatter_kwargs = {
                "s": size,
                "color": color,
                "label": label,
                "zorder": 2,
                "marker": marker,
            }
            if marker != "x":
                scatter_kwargs.update({"edgecolors": "white", "linewidth": 0.5})
            plt.scatter(xs, ys, **scatter_kwargs)

    tanks = [node for node in nodes if result["node_info"][node]["type"] == "Tank" and node in coordinates]
    if tanks:
        plt.scatter(
            [coordinates[node][0] for node in tanks],
            [coordinates[node][1] for node in tanks],
            s=50,
            marker="s",
            color="blue",
            edgecolors="white",
            linewidths=0.8,
            label="Tanks",
            zorder=4,
        )

    if not network_data.reservoirs.empty:
        reservoirs = [
            str(reservoir_id)
            for reservoir_id in network_data.reservoirs["ID"].tolist()
            if str(reservoir_id) in coordinates
        ]
        if reservoirs:
            plt.scatter(
                [coordinates[node][0] for node in reservoirs],
                [coordinates[node][1] for node in reservoirs],
                s=50,
                marker="d",
                color="green",
                edgecolors="white",
                linewidths=0.8,
                label="Reservoirs",
                zorder=5,
            )

    if not network_data.pumps.empty:
        pump_xs = []
        pump_ys = []
        for _, pump in network_data.pumps.iterrows():
            node1 = str(pump["Node1"])
            node2 = str(pump["Node2"])
            if node1 not in coordinates or node2 not in coordinates:
                continue

            x1, y1 = coordinates[node1]
            x2, y2 = coordinates[node2]
            plt.plot(
                [x1, x2],
                [y1, y2],
                color="purple",
                linewidth=1.6,
                alpha=0.8,
                zorder=3,
            )
            pump_xs.append((x1 + x2) / 2.0)
            pump_ys.append((y1 + y2) / 2.0)

        if pump_xs:
            plt.scatter(
                pump_xs,
                pump_ys,
                s=70,
                marker="h",
                color="purple",
                edgecolors="yellow",
                linewidths=1,
                label="Pumps",
                zorder=5,
            )

    print(f"\nAnnotating top {top_demand_plot} demand junction(s) per Clustering on plot...")
    
    clusters = sorted(set(labels) - {-1})
    for cluster_id in clusters:
        cluster_nodes = [node for node in nodes if node_cluster[node] == cluster_id]
        
        # 1. Thu thập tất cả các Junction và Demand của cụm này vào một list
        junction_demands = []
        for node in cluster_nodes:
            info = node_info.get(node, {})
            if info.get("type") == "Junction":
                demand = float(info.get("demand", 0.0))
                junction_demands.append((node, demand))
        
        # 2. Sắp xếp list theo Demand giảm dần (dựa vào phần tử thứ 1 trong tuple là demand)
        junction_demands.sort(key=lambda x: x[1], reverse=True)
        
        # 3. Cắt lấy số lượng điểm theo biến top_demand_plot
        top_nodes_to_plot = junction_demands[:top_demand_plot]

        # 4. Vẽ label cho từng điểm trong danh sách Top vừa cắt
        for top_node, top_demand in top_nodes_to_plot:
            if top_node in coordinates:
                x, y = coordinates[top_node]
                label = f"{top_node}\n{top_demand:.2f}"
                plt.text(
                    x,
                    y,
                    label,
                    fontsize=8,
                    fontweight="bold",
                    color="black",
                    ha="center",
                    va="bottom",
                    bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.75, "edgecolor": "black"},
                    zorder=6,
                )

    plt.xlabel("X Coordinate (m)", fontsize=11)
    plt.ylabel("Y Coordinate (m)", fontsize=11)
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\nSaved plot: {save_path}")

def get_top_demand_junctions_by_dma(result: dict, top_n: int = 5) -> pd.DataFrame:
    """Return the top N junction nodes by demand within each Clustering."""
    node_info = result["node_info"]
    node_cluster = result["node_cluster"]

    records = []
    for node, cluster in node_cluster.items():
        info = node_info.get(node, {})
        if info.get("type") != "Junction":
            continue

        records.append(
            {
                "Node_ID": node,
                "Cluster": cluster,
                "Cluster_Label": "Noise/Transit" if cluster == -1 else f"Clustering {cluster}",
                "Demand": info.get("demand", 0.0),
                "Elevation": info.get("elevation", 0.0),
                "X": info.get("x", 0.0),
                "Y": info.get("y", 0.0),
            }
        )

    if not records:
        return pd.DataFrame(
            columns=["Node_ID", "Cluster", "Cluster_Label", "Demand", "Elevation", "X", "Y"]
        )

    df = pd.DataFrame(records)
    df["Demand"] = pd.to_numeric(df["Demand"], errors="coerce").fillna(0.0)
    df = df.sort_values(["Cluster", "Demand"], ascending=[True, False])
    top_df = df.groupby("Cluster", sort=True, group_keys=False).head(top_n).reset_index(drop=True)
    return top_df

# ========================================================
# ==================== CHẠY CODE 2 =======================
print("\n" + "="*60)
print("PHASE 2: BẮT ĐẦU CHẠY CLUSTERING HDBSCAN & ĐÁNH GIÁ CHẤT LƯỢNG")
print("="*60)

# Bước 1: Trích xuất đồ thị đường ống và danh sách điểm từ dữ liệu mạng lưới (network)
print("1. Đang xây dựng đồ thị mạng lưới đường ống...")
graph, cluster_nodes, features, graph_info, node_info = build_cluster_pipe_graph(network)

# Bước 2: Tính toán ma trận khoảng cách đường đi ngắn nhất giữa tất cả các cặp điểm (Dijkstra)
print(f"2. Đang tính toán ma trận khoảng cách cho {len(cluster_nodes)} nút (Thuật toán Dijkstra)...")
distance_matrix = compute_pipe_distance_matrix(graph, cluster_nodes)

# Gọi hàm và truyền tên file INP của bạn vào
matrix = show_distance_matrix("Net3.inp")

# Bước 3: Thực thi thuật toán phân cụm mật độ HDBSCAN
if TARGET_N_CLUSTERS is not None:
    print(f"\n3. Đang tự động quét tham số để tìm cấu hình gần với {TARGET_N_CLUSTERS} cụm nhất...")
    best_result = find_hdbscan_params_for_target(distance_matrix, TARGET_N_CLUSTERS)
    clusterer = best_result["clusterer"]
    labels = best_result["labels"]
    print(f"   -> Đã chọn cấu hình tối ưu: min_cluster_size={best_result['min_cluster_size']}, min_samples={best_result['min_samples']}")
else:
    print(f"\n3. Chạy HDBSCAN thủ công với min_cluster_size={MIN_CLUSTER_SIZE}, min_samples={MIN_SAMPLES}...")
    clusterer, labels = run_hdbscan(distance_matrix, MIN_CLUSTER_SIZE, MIN_SAMPLES)

# Bước 4: Kiểm tra kết quả phân cụm thô ban đầu
n_clusters = count_clusters(labels)
raw_noise = list(labels).count(-1)
print(f"   -> Số cụm tìm được ban đầu: {n_clusters}")
print(f"   -> Số điểm bị phân loại là nhiễu (noise) ban đầu: {raw_noise}")

# Bước 5: Gán ép các điểm nhiễu (-1) về cụm DMA có khoảng cách thủy lực gần nhất
if FORCE_ASSIGN_NOISE and raw_noise > 0:
    print("\n4. Bật FORCE_ASSIGN_NOISE: Đang ép các điểm nhiễu vào cụm Clustering gần nhất...")
    labels = assign_noise_to_nearest_cluster(labels, distance_matrix)
    print(f"   -> Hoàn tất xử lý nhiễu! Số điểm nhiễu còn lại: {list(labels).count(-1)}")

# Đóng gói toàn bộ kết quả vào dictionary 'result' để truyền vào các hàm đánh giá và vẽ biểu đồ
result = {
    "clusterer": clusterer,
    "labels": labels,
    "nodes": cluster_nodes,
    "node_cluster": dict(zip(cluster_nodes, labels)),
    "node_info": node_info,
    "graph_info": graph_info,
    "distance_matrix": distance_matrix
}

# Bước 6: ĐÁNH GIÁ CHẤT LƯỢNG CLUSTER (Gọi hàm vừa bổ sung)
print("\n5. Đang đánh giá chất lượng phân cụm...")
analyze_cluster_quality(result)

# Bước 7: Trực quan hóa và vẽ kết quả lên bản đồ mạng lưới nước
print("\n6. Đang trực quan hóa các DMA lên đồ thị mạng lưới...")
cluster_image = 'hdbscan_clusters.png'
visualize_clusters(result, network, save_path=cluster_image)
print(f"-> Đã lưu ảnh kết quả phân cụm thành công tại: {cluster_image}")

# Bước 7: top demand
print(f"\n7. Đang trích xuất Top {top_n_value} nút (Junction) có nhu cầu nước (Demand) cao nhất mỗi DMA...")

try:
    top_demand_df = get_top_demand_junctions_by_dma(result, top_n=top_n_value)

    # Bước 2: Hiển thị kết quả ra màn hình Console cho dễ nhìn
    print("\n--- TOP JUNCTIONS CÓ DEMAND CAO NHẤT THEO TỪNG DMA ---")
    
    # Kỹ thuật in DataFrame đẹp, không bị gãy dòng
    if not top_demand_df.empty:
        print(top_demand_df.to_string(index=False, justify='center'))
    else:
        print("Không tìm thấy dữ liệu Junction hoặc Demand hợp lệ.")

    # Bước 3 (Tùy chọn): Lưu kết quả ra file CSV để báo cáo hoặc làm Phase 3
    output_file = "Top_Demand_Junctions_Clustering.csv"
    top_demand_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"\n-> Đã xuất danh sách thành công ra file: {output_file}")

except Exception as e:
    print(f"Lỗi khi chạy hàm lấy Demand: {e}")

# ===================================================================================================
# ============================== CODE PHASE 3 TẠO FILE LEAK INP =====================================

# Tạo file .inp leak theo số lượng Clustering tạo ra
def build_virtual_junction_276(node_info, node_cluster, pipe_list):
    """
    Create virtual node 276 based on top demand junction per cluster.
    Also generate new pipe connections.
    """

    # =========================
    # 1. group nodes by cluster
    # =========================
    clusters = defaultdict(list)

    for node, cluster in node_cluster.items():
        if cluster == -1:
            continue
        info = node_info.get(node, {})
        if info.get("type") != "Junction":
            continue
        clusters[cluster].append(node)

    # =========================
    # 2. find top demand node per cluster
    # =========================
    top_nodes = {}

    for cluster, nodes in clusters.items():
        top_node = max(
            nodes,
            key=lambda n: node_info[n].get("demand", 0)
        )
        top_nodes[cluster] = top_node

    # =========================
    # 3. build adjacency from pipes
    # =========================
    adjacency = defaultdict(list)

    for p in pipe_list:
        n1, n2 = p["start"], p["end"]
        adjacency[n1].append(n2)
        adjacency[n2].append(n1)

    # =========================
    # 4. select reference connection
    # =========================
    # pick first cluster top node and its neighbor
    cluster0 = list(top_nodes.keys())[0]
    node_a = top_nodes[cluster0]

    # pick a neighbor that is also junction
    node_b = None
    for nb in adjacency[node_a]:
        if nb in node_info:
            node_b = nb
            break

    if node_b is None:
        raise ValueError("No valid neighbor found for interpolation")

    # =========================
    # 5. interpolate node 276
    # =========================
    x1, y1 = node_info[node_a]["x"], node_info[node_a]["y"]
    x2, y2 = node_info[node_b]["x"], node_info[node_b]["y"]

    elev1 = node_info[node_a]["elevation"]
    elev2 = node_info[node_b]["elevation"]

    new_node_id = 276

    node_276 = {
        "type": "Junction",
        "demand": 0.0,
        "elevation": (elev1 + elev2) / 2,
        "x": (x1 + x2) / 2,
        "y": (y1 + y2) / 2
    }

    # =========================
    # 6. split pipe logic
    # =========================
    new_pipes = []

    split_pipe_id = None
    for p in pipe_list:
        if (p["start"] == node_a and p["end"] == node_b) or \
           (p["start"] == node_b and p["end"] == node_a):

            split_pipe_id = p["id"]
            half_len = p["length"] / 2

            new_pipes.append({
                "id": str(p["id"]) + "_1",
                "start": node_a,
                "end": new_node_id,
                "length": half_len
            })

            new_pipes.append({
                "id": str(p["id"]) + "_2",
                "start": new_node_id,
                "end": node_b,
                "length": half_len
            })

        else:
            new_pipes.append(p)

    # =========================
    # 7. return results
    # =========================
    return {
        "new_node_id": new_node_id,
        "new_node": node_276,
        "top_nodes": top_nodes,
        "updated_pipes": new_pipes,
        "split_pipe_id": split_pipe_id,
    }

def format_inp_junction_line(node_id, elevation, demand, pattern=None):
    line = f"{node_id} {elevation:.2f} {demand:.2f}"
    if pattern:
        line += f" {pattern}"
    return line + ";"

def format_inp_coordinate_line(node_id, x, y):
    return f"{node_id} {x:.2f} {y:.2f}"

def format_inp_pipe_line(original_parts, pipe):
    new_parts = [str(pipe["id"]), str(pipe["start"]), str(pipe["end"]), f"{pipe['length']:.2f}"]
    new_parts.extend(original_parts[4:])
    return " ".join(new_parts) + ";"

def _find_section_in_lines(lines, section_name):
    section_name = f"[{section_name.upper()}]"
    start = -1
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip().upper() == section_name:
            start = i
        elif start != -1 and line.strip().startswith("["):
            end = i
            break
    return start, end

def find_top_demand_junctions_per_cluster(result: dict) -> Dict[int, str]:
    top_demand = get_top_demand_junctions_by_dma(result, top_n=1)
    cluster_top = {}
    for _, row in top_demand.iterrows():
        cluster_top[int(row["Cluster"])] = str(row["Node_ID"])
    return cluster_top

def find_cluster_neighbor_pipe(top_node: str, cluster_id: int, node_cluster: Dict[str, int], pipe_list: List[Dict]) -> Tuple[Optional[Dict], Optional[str]]:
    for pipe in pipe_list:
        if pipe["start"] == top_node and node_cluster.get(pipe["end"]) == cluster_id:
            return pipe, pipe["end"]
        if pipe["end"] == top_node and node_cluster.get(pipe["start"]) == cluster_id:
            return pipe, pipe["start"]
    return None, None

def build_virtual_junction_276_for_cluster(cluster_id: int, top_node: str, other_node: str, node_info: Dict, pipe: Dict) -> dict:
    x1, y1 = node_info[top_node]["x"], node_info[top_node]["y"]
    x2, y2 = node_info[other_node]["x"], node_info[other_node]["y"]
    elevation = node_info[top_node].get("elevation", 0.0)

    new_node_id = 276
    node_276 = {
        "type": "Junction",
        "demand": 0.0,
        "elevation": elevation,
        "x": (x1 + x2) / 2,
        "y": (y1 + y2) / 2,
    }

    split_pipe_id = str(pipe["id"])
    new_pipe_id = 334

    return {
        "cluster_id": cluster_id,
        "top_node": top_node,
        "other_node": other_node,
        "new_node_id": new_node_id,
        "new_node": node_276,
        "split_pipe_id": split_pipe_id,
        "new_pipe_id": new_pipe_id,
        "original_pipe": pipe,
    }

def export_inp_with_virtual_junction(parser, virtual_result: dict, output_path: str) -> str:
    lines = parser.lines.copy()
    new_node_id = virtual_result["new_node_id"]
    new_node = virtual_result["new_node"]
    split_pipe_id = str(virtual_result.get("split_pipe_id"))
    new_pipe_id = str(virtual_result.get("new_pipe_id", 334))

    start, end = _find_section_in_lines(lines, "JUNCTIONS")
    if start == -1:
        raise ValueError("[JUNCTIONS] section not found in INP file.")

    junction_section = lines[start + 1:end]
    if not any(
        line.strip() and not line.strip().startswith(";") and line.strip().split()[0] == str(new_node_id)
        for line in junction_section
    ):
        junction_section.append(format_inp_junction_line(new_node_id, new_node["elevation"], new_node["demand"]) + "\n")
    lines = lines[: start + 1] + junction_section + lines[end:]

    start, end = _find_section_in_lines(lines, "COORDINATES")
    if start == -1:
        raise ValueError("[COORDINATES] section not found in INP file.")

    coord_section = lines[start + 1:end]
    if not any(
        line.strip() and not line.strip().startswith(";") and line.strip().split()[0] == str(new_node_id)
        for line in coord_section
    ):
        coord_section.append(format_inp_coordinate_line(new_node_id, new_node["x"], new_node["y"]) + "\n")
    lines = lines[: start + 1] + coord_section + lines[end:]

    start, end = _find_section_in_lines(lines, "PIPES")
    if start == -1:
        raise ValueError("[PIPES] section not found in INP file.")

    pipe_section = []
    appended_new_pipe = False
    original_parts = None
    for line in lines[start + 1:end]:
        data = parser._data_part(line)
        if not data or data.strip().startswith(";"):
            pipe_section.append(line)
            continue

        parts = data.split()
        if parts[0] == split_pipe_id:
            original_parts = parts
            first_half = {
                "id": split_pipe_id,
                "start": str(virtual_result["top_node"]),
                "end": str(new_node_id),
                "length": float(virtual_result["original_pipe"]["length"]) / 2,
            }
            pipe_section.append(format_inp_pipe_line(parts, first_half) + "\n")
            appended_new_pipe = True
        else:
            pipe_section.append(line)

    if not appended_new_pipe or original_parts is None:
        raise ValueError(f"Original pipe {split_pipe_id} was not found in PIPES section.")

    new_pipe = {
        "id": new_pipe_id,
        "start": new_node_id,
        "end": virtual_result["other_node"],
        "length": float(virtual_result["original_pipe"]["length"]) / 2,
    }
    pipe_section.append(format_inp_pipe_line(original_parts, new_pipe) + "\n")

    lines = lines[: start + 1] + pipe_section + lines[end:]

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return output_path

def create_276_inp_files_for_dmas(parser, result: dict, pipe_list: List[Dict], output_prefix: str = "Net3_276_DMA") -> List[str]:
    file_paths = []
    cluster_top = find_top_demand_junctions_per_cluster(result)

    for cluster_id, top_node in sorted(cluster_top.items()):
        pipe, other_node = find_cluster_neighbor_pipe(top_node, cluster_id, result["node_cluster"], pipe_list)
        if pipe is None or other_node is None:
            print(f"Skipping DMA {cluster_id}: no same-cluster pipe found for top node {top_node}.")
            continue

        virtual_result = build_virtual_junction_276_for_cluster(cluster_id, top_node, other_node, result["node_info"], pipe)
        output_path = f"{output_prefix}{cluster_id}.inp"
        try:
            file_paths.append(export_inp_with_virtual_junction(parser, virtual_result, output_path))
            print(f"Saved DMA {cluster_id} INP: {output_path}")
        except Exception as exc:
            print(f"Failed to write DMA {cluster_id} INP: {exc}")

    return file_paths

def visualize_leak_scenario(result: dict, network_data, virtual_result: dict, save_path=None):
    """
    Vẽ bản đồ mạng lưới DMA và làm nổi bật vị trí nút rò rỉ 276 cùng đường ống mới.
    """
    coordinates = network_data.coordinates
    labels = result["labels"]
    nodes = result["nodes"]
    node_cluster = result["node_cluster"]
    node_info = result["node_info"]
    graph_info = result["graph_info"]

    plt.figure(figsize=(14, 12))

    # 1. VẼ ĐƯỜNG ỐNG NỀN (Xám)
    for node1, node2, _ in graph_info["pipe_edges"]:
        if node1 in coordinates and node2 in coordinates:
            x1, y1 = coordinates[node1]
            x2, y2 = coordinates[node2]
            plt.plot([x1, x2], [y1, y2], color="gray", linewidth=1, alpha=0.6, zorder=1)

    # 2. VẼ CÁC DMA CLUSTERS
    unique_clusters = sorted(set(labels))
    cmap = plt.colormaps.get_cmap("tab20")
    color_map = {cluster: cmap(i % 20) for i, cluster in enumerate(unique_clusters)}

    for cluster_id in unique_clusters:
        cluster_nodes = [node for node in nodes if node_cluster[node] == cluster_id]
        if cluster_id == -1:
            color, label, size, marker = "black", "Noise/Transit", 40, "x"
        else:
            color, label, size, marker = color_map[cluster_id], f"DMA {cluster_id}", 60, "o"

        xs = [coordinates[node][0] for node in cluster_nodes if node in coordinates]
        ys = [coordinates[node][1] for node in cluster_nodes if node in coordinates]

        if xs:
            scatter_kwargs = {"s": size, "color": color, "label": label, "zorder": 2, "marker": marker}
            if marker != "x":
                scatter_kwargs.update({"edgecolors": "white", "linewidth": 0.5})
            plt.scatter(xs, ys, **scatter_kwargs)

    # 3. VẼ TANKS, RESERVOIRS VÀ PUMPS (Như cũ)
    tanks = [n for n in nodes if result["node_info"][n]["type"] == "Tank" and n in coordinates]
    if tanks:
        plt.scatter([coordinates[n][0] for n in tanks], [coordinates[n][1] for n in tanks],
                    s=50, marker="s", color="blue", edgecolors="white", linewidths=0.8, label="Tanks", zorder=4)

    if not network_data.reservoirs.empty:
        reservoirs = [str(r) for r in network_data.reservoirs["ID"].tolist() if str(r) in coordinates]
        if reservoirs:
            plt.scatter([coordinates[n][0] for n in reservoirs], [coordinates[n][1] for n in reservoirs],
                        s=50, marker="d", color="green", edgecolors="white", linewidths=0.8, label="Reservoirs", zorder=5)

    if not network_data.pumps.empty:
        pump_xs, pump_ys = [], []
        for _, pump in network_data.pumps.iterrows():
            n1, n2 = str(pump["Node1"]), str(pump["Node2"])
            if n1 in coordinates and n2 in coordinates:
                plt.plot([coordinates[n1][0], coordinates[n2][0]], [coordinates[n1][1], coordinates[n2][1]], color="purple", linewidth=1.6, alpha=0.8, zorder=3)
                pump_xs.append((coordinates[n1][0] + coordinates[n2][0]) / 2.0)
                pump_ys.append((coordinates[n1][1] + coordinates[n2][1]) / 2.0)
        if pump_xs:
            plt.scatter(pump_xs, pump_ys, s=70, marker="h", color="purple", edgecolors="yellow", linewidths=1, label="Pumps", zorder=5)

    # =========================================================================
    # 4. VẼ ĐIỂM RÒ RỈ 276 VÀ ỐNG MỚI (OVERLAY)
    # =========================================================================
    new_node = virtual_result["new_node"]
    top_node = virtual_result["top_node"]
    other_node = virtual_result["other_node"]
    cluster_id = virtual_result["cluster_id"]
    
    nx_coord, ny_coord = new_node["x"], new_node["y"]

    # Vẽ 2 đoạn ống bị cắt (Nổi bật bằng màu đỏ đậm)
    if top_node in coordinates and other_node in coordinates:
        tx, ty = coordinates[top_node]
        ox, oy = coordinates[other_node]
        # Ống nối Top Node -> 276
        plt.plot([tx, nx_coord], [ty, ny_coord], color='red', linewidth=3, zorder=7, label=f"Split Pipe (DMA {cluster_id})")
        # Ống nối 276 -> Other Node (Ống 334)
        plt.plot([nx_coord, ox], [ny_coord, oy], color='red', linewidth=3, zorder=7)

    # Vẽ nút 276 (Ngôi sao đỏ to)
    plt.scatter(nx_coord, ny_coord, s=100, marker='*', color='red', edgecolors='black', label='Leak Node 276', zorder=8)
    
    # Gắn nhãn text cho Nút 276 và Top Demand Node để dễ nhận diện
    plt.text(nx_coord, ny_coord + 2, '276 (Leak)', color='red', fontsize=10, fontweight='bold', ha='center', va='bottom', bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.8, "edgecolor": "red"}, zorder=9)
    
    if top_node in coordinates:
        plt.text(coordinates[top_node][0], coordinates[top_node][1] + 1, f"Top: {top_node}", color='black', fontsize=8, fontweight='bold', ha='center', va='bottom', zorder=9)

# =========================================================================

    plt.xlabel("X Coordinate (m)", fontsize=11)
    plt.ylabel("Y Coordinate (m)", fontsize=11)
    plt.title(f"Leak Scenario - DMA {cluster_id}", fontsize=14, fontweight='bold')
    
    # Đưa legend ra ngoài để không che mất bản đồ
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"   -> Đã vẽ và lưu ảnh: {save_path}")
    
    # QUAN TRỌNG: Đóng figure để giải phóng RAM khi lặp qua nhiều cụm
    plt.close()

# ===================================================================================================
# ======================================= CHẠY CODE PHASE 3 LẦN 1 =========================================
print("\n" + "="*60)
print("PHASE 3: TẠO FILE .INP VÀ VẼ HÌNH KỊCH BẢN RÒ RỈ (Nút 276, Ống 334)")
print("="*60)

if result.get("node_cluster") and not network.pipes.empty:
    
    print("1. Đang trích xuất danh sách đường ống để tìm vị trí cắt...")
    pipe_list = [
        {"id": str(row["ID"]), "start": str(row["Node1"]), "end": str(row["Node2"]), "length": float(row["Length"])}
        for _, row in network.pipes.iterrows()
    ]

    print("2. Tiến hành tạo file INP và vẽ bản đồ cho từng cụm DMA...")
    cluster_top = find_top_demand_junctions_per_cluster(result)
    
    dma_files = []
    
    # Lặp qua từng cụm (DMA 0, 1, 2... đến 9)
    for cluster_id, top_node in sorted(cluster_top.items()):
        pipe, other_node = find_cluster_neighbor_pipe(top_node, cluster_id, result["node_cluster"], pipe_list)
        if pipe is None or other_node is None:
            print(f"  [Bỏ qua] DMA {cluster_id}: Không tìm thấy đường ống nội bộ nào nối với nút Top Demand {top_node}.")
            continue

        # Tính toán thông số cho nút 276
        virtual_result = build_virtual_junction_276_for_cluster(cluster_id, top_node, other_node, result["node_info"], pipe)
        
        # 1. TẠO FILE .INP
        output_inp_path = f"leak_Cluster{cluster_id}.inp"
        try:
            dma_files.append(export_inp_with_virtual_junction(parser, virtual_result, output_inp_path))
            print(f"\nĐã lưu file INP: {output_inp_path}")
            
            # 2. VẼ ẢNH KỊCH BẢN (Gọi hàm mới ở đây)
            output_img_path = f"Leak_Image_{cluster_id}.png"
            visualize_leak_scenario(result, network, virtual_result, save_path=output_img_path)
            
        except Exception as exc:
            print(f"Lỗi khi xử lý DMA {cluster_id}: {exc}")

    print(f"\n=> HOÀN TẤT! Đã tạo thành công {len(dma_files)} kịch bản rò rỉ (INP + Hình ảnh minh họa).")
else:
    print("Lỗi: Dữ liệu mạng lưới (network) hoặc kết quả phân cụm (result) không tồn tại!")


# ===================================================================================================
# ========================= CODE PHASE 3 TẠO DEMAND 20% VÀ MÔ PHỎNG LEAK ============================
# hàm tạo 20% biến động ngẫu nhiên cho demand của tất cả các junctions và lưu thành file CSV
def generate_random_demand_csv(inp_file, n_scenarios, output_csv):
    wn1 = wntr.network.WaterNetworkModel(inp_file)
    junctions = wn1.junction_name_list

    # lấy base demand
    base_demands = np.array([
        wn1.get_node(j).base_demand for j in junctions
    ])
    
    scenarios = []
    for s in range(n_scenarios):
        # random ±20%
        rand_factor = np.random.uniform(0.8, 1.2, len(junctions))
        # demand mới
        new_demands = base_demands * rand_factor
        scenarios.append(new_demands)

    df = pd.DataFrame(scenarios, columns=junctions)
    df.to_csv(output_csv, index=False)
    print("Saved:", output_csv)

# Tạo file demand ngẫu nhiên (Chỉ cần chạy 1 lần dựa trên Net3.inp)
if not os.path.exists(save_file):
    generate_random_demand_csv(
        inp_file=data_path,
        n_scenarios=1000,
        output_csv=save_file
    )

# KHỞI TẠO MỐC THỜI GIAN: Lấy dữ liệu mỗi giờ một lần (Từ 0h đến 24h)
# 3600 giây = 1 giờ
time_steps = [hr * 3600 for hr in range(0, 25)] 

# Đọc file demand đã được tạo ngẫu nhiên
df_demands = pd.read_csv(demand_csv)

# ==========================================
# THÊM VÒNG LẶP FOR QUÉT QUA CÁC FILE .INP
# ==========================================
# Tìm tất cả các file có dạng leak_Cluster{x}.inp trong thư mục
# leak_files = glob.glob('leak_Cluster*.inp')

# if not leak_files:
#     print("Không tìm thấy file rò rỉ nào có tên 'leak_Cluster*.inp'. Vui lòng kiểm tra lại!")
# else:
#     for leak_file in leak_files:
#         # Tự động tạo tên file output dựa trên tên file .inp
#         # Ví dụ: leak_Cluster0.inp -> leak_Cluster0_TimeSeries_LeakArea_Dataset.csv
#         base_name = os.path.splitext(os.path.basename(leak_file))[0]
#         output_dataset = f'{base_name}_TimeSeries_LeakArea_Dataset.csv'
        
#         print("\n" + "="*60)
#         # ==========================================
#         # 2. KHỞI TẠO MÔ HÌNH CHO FILE HIỆN TẠI
#         # ==========================================
#         print(f"-> Đang nạp mạng lưới ({leak_file}) và kịch bản Demand...")
#         wn_goc = wntr.network.WaterNetworkModel(leak_file)

#         dataset_rows = []
#         start_time = time.time()
#         total_sims = len(df_demands) * len(leak_areas)
#         count = 0

#         # ==========================================
#         # 3. VÒNG LẶP SINH DỮ LIỆU
#         # ==========================================
#         for row_index, demand_row in df_demands.iterrows():
            
#             for area in leak_areas:
#                 count += 1
#                 print(f"[{base_name}] Tiến độ mô phỏng: {count}/{total_sims} | Leak Area: {area} m2", end='\r')
                
#                 wn_sim = copy.deepcopy(wn_goc)
                
#                 # Ghi đè Demand
#                 for node_id, new_demand in demand_row.items():
#                     node_name = str(node_id)
#                     if node_name in wn_sim.junction_name_list:
#                         node = wn_sim.get_node(node_name)
#                         if len(node.demand_timeseries_list) > 0:
#                             node.demand_timeseries_list[0].base_value = new_demand
                            
#                 # Gán Demand nút rò rỉ về 0
#                 try:
#                     leak_node = wn_sim.get_node(leak_node_id)
#                     if len(leak_node.demand_timeseries_list) > 0:
#                         leak_node.demand_timeseries_list[0].base_value = 0
                            
#                     # Kích hoạt rò rỉ
#                     leak_node.emitter_coefficient = area * 500
#                 except KeyError:
#                     pass # Đề phòng kịch bản không có nút 276
                
#                 # Chạy mô phỏng
#                 sim = wntr.sim.EpanetSimulator(wn_sim)
#                 try:
#                     results = sim.run_sim()
                    
#                     # Lấy nguyên cái bảng áp suất 24h (Index là thời gian, Columns là các Nút)
#                     pressure_all_times = results.node['pressure']
                    
#                     # ==========================================
#                     # 4. LẶP QUA TỪNG GIỜ ĐỂ LƯU DATA TIME SERIES
#                     # ==========================================
#                     for t_step in time_steps:
#                         # Nếu thời gian này có tồn tại trong kết quả
#                         if t_step in pressure_all_times.index:
#                             pressure_row = pressure_all_times.loc[t_step]
                            
#                             # Dòng dữ liệu giờ có thêm cột Time_Hour
#                             data_record = {
#                                 'Scenario_ID': row_index,
#                                 'Leak_Node': leak_node_id, 
#                                 'Leak_Area': area,
#                                 'Time_Hour': t_step / 3600  # Đổi ra giờ cho dễ đọc (0, 1, 2... 24)
#                             }
                            
#                             # Đổ áp suất của toàn bộ cảm biến vào
#                             for node_name, p_val in pressure_row.items():
#                                 data_record[node_name] = p_val
                                
#                             dataset_rows.append(data_record)
#                 except:
#                     continue # Bỏ qua nếu lỗi thủy lực

#         # ==========================================
#         # 5. XUẤT FILE DATASET
#         # ==========================================
#         df_final = pd.DataFrame(dataset_rows)
#         df_final.to_csv(output_dataset, index=False)
#         print(f"\n-> Xong! Dataset TimeSeries đã sẵn sàng tại: {output_dataset}")
#         print(f"Kích thước ma trận: {df_final.shape[0]} dòng x {df_final.shape[1]} cột.")


# ===================================================================================================
# ================================== CODE PHASE 4 TÍNH TOÁN ENTROPY =================================
def load_sensor_entropy_data(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    drop_cols = [c for c in ['1', '2', '3', 'River', 'Lake'] if c in df.columns]
    return df.drop(columns=drop_cols, errors='ignore')

def get_valid_sensor_columns(df: pd.DataFrame, coords: Dict[str, Tuple[float, float]]) -> list:
    exclude_cols = {'Scenario_ID', 'Leak_Node', 'Leak_Area', 'Time_Hour'}
    return [c for c in df.columns if c not in exclude_cols and str(c) in coords]

def calculate_entropy(series, num_bins=15):
    arr = np.array(series)
    arr = np.where(np.abs(arr) < 1e-3, 0.0, arr)
    if np.min(arr) == np.max(arr):
        return 0.0
    counts, _ = np.histogram(arr, bins=num_bins)
    probs = counts[counts > 0] / len(arr)
    return -np.sum(probs * np.log2(probs))

def compute_entropy_series(df: pd.DataFrame, sensor_cols: list, num_bins: int = 15) -> pd.Series:
    return pd.Series({s: calculate_entropy(df[s], num_bins) for s in sensor_cols})

def build_cluster_entropy_dataframe(entropy_series: pd.Series, result: dict) -> pd.DataFrame:
    rows = []
    for node_id, entropy in entropy_series.items():
        if node_id not in result['node_cluster']:
            continue
        info = result['node_info'].get(node_id, {})
        if info.get('type') != 'Junction':
            continue
        cluster = result['node_cluster'][node_id]
        rows.append(
            {
                'Node_ID': node_id,
                'Cluster': cluster,
                'Cluster_Label': 'Noise/Transit' if cluster == -1 else f'DMA {cluster}',
                'Entropy': float(entropy),
                'Elevation': float(info.get('elevation', 0.0)),
                'Demand': float(info.get('demand', 0.0)),
                'X': float(info.get('x', 0.0)),
                'Y': float(info.get('y', 0.0)),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(['Cluster', 'Entropy'], ascending=[True, False]).reset_index(drop=True)
    return df

def visualize_top_entropy_sensors(result: dict, network_data, entropy_df: pd.DataFrame, top_n_entropy: int = 1, save_path=None):
    """
    Vẽ bản đồ mạng lưới DMA và làm nổi bật các vị trí Junction có Entropy cao nhất 
    (đề xuất đặt Cảm biến rò rỉ - Sensor) cho từng cụm.
    """
    coordinates = network_data.coordinates
    labels = result["labels"]
    nodes = result["nodes"]
    node_cluster = result["node_cluster"]
    node_info = result["node_info"]
    graph_info = result["graph_info"]

    plt.figure(figsize=(14, 12))

    # =========================================================================
    # 1. VẼ ĐƯỜNG ỐNG NỀN (Xám)
    # =========================================================================
    for node1, node2, _ in graph_info["pipe_edges"]:
        if node1 in coordinates and node2 in coordinates:
            x1, y1 = coordinates[node1]
            x2, y2 = coordinates[node2]
            plt.plot([x1, x2], [y1, y2], color="gray", linewidth=1, alpha=0.6, zorder=1)

    # =========================================================================
    # 2. VẼ CÁC DMA CLUSTERS
    # =========================================================================
    unique_clusters = sorted(set(labels))
    cmap = plt.colormaps.get_cmap("tab20")
    color_map = {cluster: cmap(i % 20) for i, cluster in enumerate(unique_clusters)}

    for cluster_id in unique_clusters:
        cluster_nodes = [node for node in nodes if node_cluster[node] == cluster_id]

        if cluster_id == -1:
            color, label, size, marker = "black", "Noise/Transit", 40, "x"
        else:
            color, label, size, marker = color_map[cluster_id], f"DMA {cluster_id}", 60, "o"

        xs = [coordinates[node][0] for node in cluster_nodes if node in coordinates]
        ys = [coordinates[node][1] for node in cluster_nodes if node in coordinates]

        if xs:
            scatter_kwargs = {"s": size, "color": color, "label": label, "zorder": 2, "marker": marker}
            if marker != "x":
                scatter_kwargs.update({"edgecolors": "white", "linewidth": 0.5})
            plt.scatter(xs, ys, **scatter_kwargs)

    # =========================================================================
    # 3. VẼ TANKS, RESERVOIRS VÀ PUMPS
    # =========================================================================
    tanks = [node for node in nodes if result["node_info"][node]["type"] == "Tank" and node in coordinates]
    if tanks:
        plt.scatter([coordinates[n][0] for n in tanks], [coordinates[n][1] for n in tanks],
                    s=50, marker="s", color="blue", edgecolors="white", linewidths=0.8, label="Tanks", zorder=4)

    if not network_data.reservoirs.empty:
        reservoirs = [str(r) for r in network_data.reservoirs["ID"].tolist() if str(r) in coordinates]
        if reservoirs:
            plt.scatter([coordinates[n][0] for n in reservoirs], [coordinates[n][1] for n in reservoirs],
                        s=50, marker="d", color="green", edgecolors="white", linewidths=0.8, label="Reservoirs", zorder=5)

    if not network_data.pumps.empty:
        pump_xs, pump_ys = [], []
        for _, pump in network_data.pumps.iterrows():
            n1, n2 = str(pump["Node1"]), str(pump["Node2"])
            if n1 in coordinates and n2 in coordinates:
                plt.plot([coordinates[n1][0], coordinates[n2][0]], [coordinates[n1][1], coordinates[n2][1]], color="purple", linewidth=1.6, alpha=0.8, zorder=3)
                pump_xs.append((coordinates[n1][0] + coordinates[n2][0]) / 2.0)
                pump_ys.append((coordinates[n1][1] + coordinates[n2][1]) / 2.0)
        if pump_xs:
            plt.scatter(pump_xs, pump_ys, s=70, marker="h", color="purple", edgecolors="yellow", linewidths=1, label="Pumps", zorder=5)

    # =========================================================================
    # 4. VẼ VỊ TRÍ ĐẶT SENSOR (TOP ENTROPY JUNCTIONS)
    # =========================================================================
    print(f"\nAnnotating top {top_n_entropy} entropy junction(s) per Clustering on plot...")
    
    # Kiểm tra xem entropy_df có trống và có đủ cột không
    if not entropy_df.empty and 'Entropy' in entropy_df.columns and 'Cluster' in entropy_df.columns:
        clusters = sorted(set(labels) - {-1}) # Bỏ qua điểm nhiễu -1
        
        for cluster_id in clusters:
            # Lọc dữ liệu của cluster hiện tại
            cluster_data = entropy_df[entropy_df['Cluster'] == cluster_id]
            
            # Sắp xếp theo Entropy giảm dần và cắt lấy số lượng theo top_n_entropy
            top_sensors = cluster_data.sort_values(by='Entropy', ascending=False).head(top_n_entropy)
            
            for rank, (_, row) in enumerate(top_sensors.iterrows(), start=1):
                sensor_node = str(row['Node_ID'])
                entropy_val = float(row['Entropy'])
                
                if sensor_node in coordinates:
                    sx, sy = coordinates[sensor_node]
                    
                    # Vẽ điểm Sensor: Dùng Ngôi sao (star) to, màu vàng, viền xanh đen để phân biệt với Leak (viền đỏ)
                    plt.scatter(sx, sy, s=250, marker='*', color='gold', edgecolors='midnightblue', linewidths=1.5, zorder=8)
                    
                    # Gắn nhãn hiển thị ID và giá trị Entropy
                    label_text = f"Sensor {rank}\nID:{sensor_node}\nH:{entropy_val:.2f}"
                    plt.text(
                        sx, sy + 1.5, 
                        label_text, 
                        fontsize=9, 
                        fontweight='bold', 
                        color='midnightblue', 
                        ha='center', 
                        va='bottom', 
                        bbox={"boxstyle": "round,pad=0.3", "facecolor": "lightyellow", "alpha": 0.85, "edgecolor": "gold"}, 
                        zorder=9
                    )

    plt.xlabel("X Coordinate (m)", fontsize=11)
    plt.ylabel("Y Coordinate (m)", fontsize=11)
    plt.title(f"Optimal Sensor Placement (Top {top_n_entropy} Entropy per DMA)", fontsize=14, fontweight='bold')
    
    # Custom 1 dòng cho legend đại diện Sensor
    plt.scatter([], [], s=150, marker='*', color='gold', edgecolors='midnightblue', label='Proposed Sensor')
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"   -> Đã vẽ và lưu ảnh phân bố Sensor: {save_path}")
        
    plt.close()

# ===================================================================================================
# ==================================== CHẠY CODE PHASE 4 ENTROPY ====================================
print("\n" + "="*60)
print("PHASE 4: TÍNH TOÁN ENTROPY TOÀN CỤC VÀ ĐỀ XUẤT VỊ TRÍ SENSOR")
print("="*60)

# 1. Tìm tất cả các file dataset đã sinh ra từ Phase 3
dataset_files = glob.glob('*_TimeSeries_LeakArea_Dataset.csv')

if not dataset_files:
    print("Không tìm thấy file dữ liệu mô phỏng nào! Hãy chắc chắn Phase 3 đã chạy thành công.")
else:
    print(f"1. Đang gộp dữ liệu từ {len(dataset_files)} file kịch bản rò rỉ...")
    
    # Đọc và làm sạch từng file, sau đó đưa vào 1 list
    df_list = []
    for file in dataset_files:
        df_clean = load_sensor_entropy_data(file)
        df_list.append(df_clean)
        
    # Gộp tất cả thành một Master DataFrame (Bao gồm mọi kịch bản rò rỉ trên toàn mạng lưới)
    master_df = pd.concat(df_list, ignore_index=True)
    print(f"   -> Đã tạo Master Dataset với kích thước: {master_df.shape[0]} dòng, {master_df.shape[1]} cột.")

    # 2. Lọc danh sách các Node hợp lệ để tính Entropy (Chỉ lấy các nút có trong mạng lưới)
    sensor_cols = get_valid_sensor_columns(master_df, network.coordinates)
    print(f"2. Đã xác định được {len(sensor_cols)} vị trí Junction hợp lệ để tính Entropy.")

    # 3. Tính toán chuỗi Entropy cho toàn bộ các nút
    print("3. Đang tính toán Shannon Entropy cho từng vị trí... (Quá trình này có thể mất vài giây)")
    entropy_series = compute_entropy_series(master_df, sensor_cols, num_bins=15)

    # 4. Gắn kết quả Entropy vào các cụm DMA và sắp xếp
    cluster_entropy_df = build_cluster_entropy_dataframe(entropy_series, result)
    
    # Lưu kết quả tính toán ra file CSV để báo cáo
    entropy_result_file = "Entropy_Sensor_Placement_Result.csv"
    cluster_entropy_df.to_csv(entropy_result_file, index=False)
    print(f"4. Đã lưu bảng xếp hạng Entropy thành công ra file: {entropy_result_file}")

    # Hiển thị Top 1 (hoặc số lượng tùy chọn) Sensor mỗi DMA ra màn hình
    print("\n--- ĐỀ XUẤT TOP VỊ TRÍ ĐẶT CẢM BIẾN THEO DMA ---")
    top_1_sensors = cluster_entropy_df.groupby('Cluster').head(1)
    print(top_1_sensors[['Cluster_Label', 'Node_ID', 'Entropy', 'Demand']].to_string(index=False))

    # 5. Vẽ bản đồ phân bố cảm biến
    print("\n5. Đang trực quan hóa vị trí Sensor lên bản đồ...")
    sensor_plot_file = "Optimal_Sensors_Distribution.png"
    
    # Giả sử bạn đã khai báo TOP_ENTROPY_PLOT = 2 ở đầu file
    top_plot_val = globals().get('TOP_ENTROPY_PLOT', 1) 
    
    visualize_top_entropy_sensors(
        result=result, 
        network_data=network, 
        entropy_df=cluster_entropy_df, 
        top_n_entropy=top_plot_val, 
        save_path=sensor_plot_file
    )
    
    print("\n" + "="*60)
    print("HOÀN TẤT TOÀN BỘ QUÁ TRÌNH PHÂN TÍCH!")
    print("="*60)

# ================================================================================
# LAST MA TRẬN COV ĐÁNH GIÁ BAO PHỦ
def build_sensitivity_matrix(inp_file: str, sensors: list, leak_area: float = 0.01) -> pd.DataFrame:
    """
    Chạy mô phỏng rò rỉ tại TẤT CẢ các Junction để lập ma trận (Sensor x Junction).
    Lưu ý: Quá trình này sẽ tốn thời gian tùy thuộc vào số lượng nút trong mạng lưới.
    """
    wn = wntr.network.WaterNetworkModel(inp_file)
    junctions = wn.junction_name_list
    
    # 1. Chạy kịch bản gốc (Không rò rỉ) để lấy áp suất nền
    sim_base = wntr.sim.EpanetSimulator(wn)
    res_base = sim_base.run_sim()
    # Lấy áp suất tại giờ thứ 12 (hoặc giờ bạn muốn) làm chuẩn
    base_pressure = res_base.node['pressure'].loc[12*3600, sensors]
    
    # Khởi tạo ma trận (Hàng: Sensor, Cột: Junction)
    matrix = pd.DataFrame(index=sensors, columns=junctions)
    
    print(f"Đang mô phỏng {len(junctions)} kịch bản rò rỉ để lập ma trận độ nhạy...")
    
    # 2. Quét rò rỉ qua từng Junction
    for j_id in tqdm(junctions):
        wn_leak = copy.deepcopy(wn)
        leak_node = wn_leak.get_node(j_id)
        
        # Tạo rò rỉ: Emitter coefficient = C_d * Area * (2g)^0.5. Hệ số đơn giản hóa là diện tích * hằng số
        leak_node.emitter_coefficient = leak_area * 500 
        
        try:
            sim_leak = wntr.sim.EpanetSimulator(wn_leak)
            res_leak = sim_leak.run_sim()
            leak_pressure = res_leak.node['pressure'].loc[12*3600, sensors]
            
            # Tính độ chênh lệch áp suất tuyệt đối |P_leak - P_base|
            delta_p = np.abs(leak_pressure - base_pressure)
            matrix[j_id] = delta_p
        except Exception:
            # Nếu mô phỏng lỗi (áp suất âm, không hội tụ), đánh giá chênh lệch = 0
            matrix[j_id] = 0.0
            
    return matrix

def calculate_coverage(sensitivity_matrix: pd.DataFrame, threshold: float = 0.5):
    """
    Đánh giá độ bao phủ dùng hàm f(x) = max(0, x - threshold).
    Trả về ma trận đã lọc nhiễu, danh sách nút được bao phủ và tỷ lệ %.
    """
    # Áp dụng hàm max(0, x - threshold) cho toàn bộ ma trận
    effective_matrix = sensitivity_matrix.applymap(lambda x: max(0, x - threshold))
    
    # Tổng hợp theo cột (Junction). Nếu tổng > 0 nghĩa là có ít nhất 1 sensor phát hiện được.
    is_covered = effective_matrix.sum(axis=0) > 0
    
    covered_nodes = is_covered[is_covered == True].index.tolist()
    uncovered_nodes = is_covered[is_covered == False].index.tolist()
    
    coverage_percent = (len(covered_nodes) / len(sensitivity_matrix.columns)) * 100
    
    return effective_matrix, covered_nodes, uncovered_nodes, coverage_percent

def visualize_coverage_map(network_data, sensors: list, covered_nodes: list, uncovered_nodes: list, save_path=None):
    """
    Vẽ bản đồ thể hiện vùng bao phủ của các cảm biến.
    """
    coords = network_data.coordinates
    plt.figure(figsize=(14, 12))
    
    # Vẽ đường ống
    if not network_data.pipes.empty:
        for _, pipe in network_data.pipes.iterrows():
            if pipe['Node1'] in coords and pipe['Node2'] in coords:
                x1, y1 = coords[pipe['Node1']]
                x2, y2 = coords[pipe['Node2']]
                plt.plot([x1, x2], [y1, y2], color="lightgray", linewidth=1, alpha=0.5, zorder=1)

    # Nút KHÔNG được bao phủ (Màu đỏ/xám nhạt)
    ux = [coords[n][0] for n in uncovered_nodes if n in coords]
    uy = [coords[n][1] for n in uncovered_nodes if n in coords]
    plt.scatter(ux, uy, c='lightcoral', s=30, label='Uncovered Junctions', alpha=0.6, zorder=2)

    # Nút ĐƯỢC bao phủ (Màu xanh dương)
    cx = [coords[n][0] for n in covered_nodes if n in coords]
    cy = [coords[n][1] for n in covered_nodes if n in coords]
    plt.scatter(cx, cy, c='dodgerblue', s=40, label='Covered Junctions', edgecolors='white', linewidths=0.5, zorder=3)

    # Cảm biến (Ngôi sao vàng)
    sx = [coords[n][0] for n in sensors if n in coords]
    sy = [coords[n][1] for n in sensors if n in coords]
    plt.scatter(sx, sy, c='gold', marker='*', s=300, edgecolors='black', linewidths=1.5, label='Sensors', zorder=4)

    plt.title(f"Sensor Coverage Map (Coverage: {(len(covered_nodes)/(len(covered_nodes)+len(uncovered_nodes))*100):.1f}%)", fontsize=14, fontweight='bold')
    plt.xlabel("X Coordinate")
    plt.ylabel("Y Coordinate")
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.axis("equal")
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

# ===============================================================================================================
# ============================================ CHẠY MA TRẬN BAO PHỦ =============================================
print("\n" + "-"*50)
print("BƯỚC CUỐI CÙNG: ĐÁNH GIÁ ĐỘ BAO PHỦ CỦA CẢM BIẾN (COVERAGE)")
print("-"*50)

# Lấy danh sách Node ID của các Top Sensor (Ví dụ mỗi cụm chọn 1 sensor)
top_sensors_list = cluster_entropy_df.groupby('Cluster').head(1)['Node_ID'].astype(str).tolist()
    
# Khai báo ngưỡng nhiễu (Threshold) - Ví dụ 0.5 mét cột nước
NOISE_THRESHOLD = 0.5 
    
# 1. Xây dựng ma trận độ nhạy (Sensor x Toàn bộ Junctions)
sensitivity_matrix = build_sensitivity_matrix(
    inp_file=data_path, 
    sensors=top_sensors_list, 
    leak_area=0.01
)

# 2. Áp dụng Threshold tính độ bao phủ
eff_matrix, covered, uncovered, cov_percent = calculate_coverage(sensitivity_matrix, threshold=NOISE_THRESHOLD)
    
print(f"\n-> Kết quả Độ bao phủ với ngưỡng nhiễu {NOISE_THRESHOLD}m:")
print(f"   + Tổng số Junctions     : {len(covered) + len(uncovered)}")
print(f"   + Số Junctions bao phủ  : {len(covered)}")
print(f"   + Tỷ lệ bao phủ (Coverage) : {cov_percent:.2f}%")
    
# 3. Vẽ bản đồ kết quả
coverage_img = "Sensor_Coverage_Map.png"
visualize_coverage_map(network, top_sensors_list, covered, uncovered, save_path=coverage_img)
print(f"-> Đã lưu bản đồ bao phủ tại: {coverage_img}")
