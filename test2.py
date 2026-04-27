import wntr
import pandas as pd
import numpy as np

# ==========================================
# 1. ĐỌC TỌA ĐỘ TỪ FILE BẢN ĐỒ GỐC (NET3)
# ==========================================
inp_file = 'Net3.inp'
wn = wntr.network.WaterNetworkModel(inp_file)

# Lấy tọa độ của các nút gốc
coords = {}
for name, node in wn.nodes():
    coords[name] = node.coordinates

def get_distance(node1, node2):
    c1 = coords[str(node1)]
    c2 = coords[str(node2)]
    return np.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)

# ==========================================
# 2. ĐỌC DỮ LIỆU ENTROPY TỪ FILE MÔ PHỎNG LEAK
# ==========================================
csv_file = '113_TimeSeries_LeakArea_Dataset.csv' 
df = pd.read_csv(csv_file)

# Lấy tất cả các cột tiềm năng
all_potential_cols = [c for c in df.columns if c not in ['Scenario_ID', 'Leak_Node', 'Leak_Area', 'Time_Hour']]

# BỘ LỌC QUAN TRỌNG: Chỉ lấy các cột CÓ TỒN TẠI trong file Net3.inp
# Bước này tự động "đá" nút 276 ra khỏi danh sách tính toán tọa độ
sensor_cols = [col for col in all_potential_cols if str(col) in coords]

# ==========================================
# 3. TÍNH TOÁN ENTROPY & TƯƠNG QUAN
# ==========================================
print(f"-> Đã đối chiếu: Tìm thấy {len(sensor_cols)} nút hợp lệ trên bản đồ Net3 gốc.")

def calculate_entropy(series, num_bins=15):
    counts, _ = np.histogram(series, bins=num_bins)
    probs = counts[counts > 0] / len(series)
    return -np.sum(probs * np.log2(probs))

# Chỉ tính trên các sensor_cols đã được lọc
entropy_series = pd.Series({s: calculate_entropy(df[s], 15) for s in sensor_cols})

# Chuẩn hóa về [0, 1]
normalized_entropy = (entropy_series - entropy_series.min()) / (entropy_series.max() - entropy_series.min())

# Tính độ tương quan (Redundancy)
corr_matrix = df[sensor_cols].corr().abs()

# ==========================================
# 4. THUẬT TOÁN SPATIO-mRMR TRÊN BẢN ĐỒ NET3
# ==========================================
num_sensors = 10  # Số lượng cảm biến muốn chọn
selected_sensors = []
unselected_sensors = list(sensor_cols)

# Các thông số Ràng buộc Không gian
MIN_DISTANCE_THRESHOLD = 8  # Bán kính cấm (Bạn có thể tinh chỉnh số này)
ALPHA_PENALTY = 2            # Trọng số phạt trùng lặp dữ liệu

print("\n=== KẾT QUẢ QUY HOẠCH CẢM BIẾN (SPATIO-mRMR) ===")

# Chọn Cảm biến 1
first_sensor = normalized_entropy.idxmax()
selected_sensors.append(first_sensor)
unselected_sensors.remove(first_sensor)
print(f"Cảm biến #1: Nút {first_sensor} (Entropy Max: {entropy_series[first_sensor]:.4f})")

# Chọn các Cảm biến tiếp theo
for step in range(1, num_sensors):
    mrmr_scores = {}
    for candidate in unselected_sensors:
        # Kiểm tra điều kiện Không gian: Có quá gần nút đã chọn không?
        min_dist_to_selected = min([get_distance(candidate, s) for s in selected_sensors])
        
        if min_dist_to_selected < MIN_DISTANCE_THRESHOLD:
            continue # Vi phạm bán kính cấm -> Bỏ qua
            
        # Nếu vượt qua, tính điểm mRMR
        relevance = normalized_entropy[candidate]
        redundancy = np.mean([corr_matrix.loc[candidate, s] for s in selected_sensors])
        score = relevance - (ALPHA_PENALTY * redundancy)
        mrmr_scores[candidate] = score
        
    if not mrmr_scores:
        print(f"\n[Cảnh báo] Bán kính {MIN_DISTANCE_THRESHOLD} quá lớn, không còn nút nào trống! Đang dừng lại ở {len(selected_sensors)} cảm biến.")
        break
        
    best_next_sensor = max(mrmr_scores, key=mrmr_scores.get)
    selected_sensors.append(best_next_sensor)
    unselected_sensors.remove(best_next_sensor)
    
    print(f"Cảm biến #{step+1}: Nút {best_next_sensor} (Entropy: {entropy_series[best_next_sensor]:.4f} | Cách nút gần nhất: {min([get_distance(best_next_sensor, s) for s in selected_sensors[:-1]]):.0f})")

print(f"\n=> Danh sách {len(selected_sensors)} cảm biến TOÀN DIỆN trên Net3: {selected_sensors}")