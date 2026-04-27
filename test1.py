import wntr
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd 
import copy
import time

inp_file = 'Net3.inp'
save_file = 'demand_scenarios.csv'
csv_file = 'demand_scenarios.csv'
inp_file = '113.inp'          
demand_csv = 'demand_scenarios.csv'
output_dataset = '113_TimeSeries_LeakArea_Dataset.csv' 

#  ==============================================================================
# 1. Khởi tạo và chạy mô phỏng
# (Đổi 'Net3.inp' thành tên file mạng lưới của bạn)
wn = wntr.network.WaterNetworkModel(inp_file)
sim = wntr.sim.EpanetSimulator(wn)
results = sim.run_sim()

# 2. Trích xuất và hiển thị thông tin về Junctions, Reservoirs, và Tanks
print("--- THÔNG TIN JUNCTIONS ---")
for j in wn.junction_name_list:
    node = wn.get_node(j)
    print(j, node.base_demand)

# Lấy dữ liệu Cột áp (Head) và Áp suất (Pressure) của toàn mạng lưới
head_data = results.node['head']
pressure_data = results.node['pressure']

print("--- THÔNG TIN RESERVOIR (NGUỒN VÔ HẠN) ---")
# Cột áp của Reservoir thường cố định hoặc thay đổi theo một mẫu (pattern) cài đặt sẵn
for res in wn.reservoir_name_list:
    # Lấy cột áp tại thời điểm đầu tiên (t=0)
    res_head = head_data[res].iloc[0]
    print(f"Cột áp tại nguồn [{res}]: {res_head:.2f} m")

print("\n--- THÔNG TIN TANK (BỂ CHỨA) ---")
# Trong WNTR, 'pressure' tại Tank chính là chiều cao mực nước (Water Level) trong bể
for tank in wn.tank_name_list:
    # Trích xuất mực nước đầu ngày và cuối chu kỳ mô phỏng
    level_start = pressure_data[tank].iloc[0]
    level_end = pressure_data[tank].iloc[-1]
    
    # Bạn cũng có thể lấy các thông số vật lý của bể từ mô hình gốc
    tank_obj = wn.get_node(tank)
    max_level = tank_obj.max_level
    min_level = tank_obj.min_level
    
    print(f"Bể [{tank}]:")
    print(f"  - Mực nước ban đầu: {level_start:.2f} m")
    print(f"  - Mực nước kết thúc: {level_end:.2f} m")
    print(f"  - Giới hạn bể: {min_level:.1f}m (Min) -> {max_level:.1f}m (Max)")


#  ==============================================================================
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
        new_demands = base_demands *  rand_factor

        scenarios.append(new_demands)

    df = pd.DataFrame(scenarios, columns=junctions)

    df.to_csv(output_csv, index=False)

    print("Saved:", output_csv)

generate_random_demand_csv(
    inp_file=inp_file,
    n_scenarios=1000,
    output_csv=save_file
)

#  ==============================================================================

def export_new_inp_file(original_inp, demand_csv, scenario_row_index, output_filename):
    # 1. Load mạng lưới gốc
    wn2 = wntr.network.WaterNetworkModel(original_inp)
    
    # 2. Đọc file CSV bình thường (BỎ index_col='scenario' đi)
    df_demands = pd.read_csv(demand_csv)
    
    # Kiểm tra xem dòng yêu cầu có vượt quá số dòng trong file không
    if scenario_row_index >= len(df_demands):
        print(f"Lỗi: File CSV chỉ có {len(df_demands)} kịch bản, không tìm thấy dòng {scenario_row_index}.")
        return

    # 3. Lấy dữ liệu kịch bản bằng CHỈ SỐ DÒNG (dùng .iloc)
    # Ví dụ scenario_row_index = 0 sẽ lấy dòng đầu tiên
    scenario_data = df_demands.iloc[scenario_row_index]
    
    # 4. Cập nhật Demand vào mạng lưới
    for node_id, new_demand in scenario_data.items():
        node_name = str(node_id)
        if node_name in wn2.junction_name_list:
            node = wn2.get_node(node_name)
            if len(node.demand_timeseries_list) > 0:
                # Ghi đè giá trị base_value
                node.demand_timeseries_list[0].base_value = new_demand

    # 5. Xuất ra file .inp mới
    wntr.network.write_inpfile(wn2, output_filename, units=wn2.options.hydraulic.inpfile_units)
    print(f"Đã tạo thành công file: {output_filename}")

# ==========================================
# GỌI HÀM ĐỂ CHẠY       
# Thay vì gọi 'scenario_0', bây giờ ta gọi số 0 (tương ứng dòng đầu tiên)
# ==========================================
export_new_inp_file('Net3.inp', 'demand_scenarios.csv', 0, 'Net3_Scenario_0.inp')

import wntr
import pandas as pd
import numpy as np
import copy
import time

# ==========================================
# 1. CÀI ĐẶT THÔNG SỐ ĐẦU VÀO
# ==========================================

leak_node_id = '276'  
leak_areas = [0.001, 0.005, 0.01, 0.02, 0.05] 
discharge_coeff = 0.75

# KHỞI TẠO MỐC THỜI GIAN: Lấy dữ liệu mỗi giờ một lần (Từ 0h đến 24h)
# 3600 giây = 1 giờ
time_steps = [hr * 3600 for hr in range(0, 25)] 

# ==========================================
# 2. KHỞI TẠO MÔ HÌNH
# ==========================================
print(f"-> Đang nạp mạng lưới 191 và kịch bản Demand...")
wn_goc = wntr.network.WaterNetworkModel(inp_file)
df_demands = pd.read_csv(demand_csv)

dataset_rows = []
start_time = time.time()
total_sims = len(df_demands) * len(leak_areas)
count = 0

# ==========================================
# 3. VÒNG LẶP SINH DỮ LIỆU
# ==========================================
for row_index, demand_row in df_demands.iterrows():
    
    for area in leak_areas:
        count += 1
        print(f"Tiến độ mô phỏng: {count}/{total_sims} | Leak Area: {area} m2", end='\r')
        
        wn_sim = copy.deepcopy(wn_goc)
        
        # Ghi đè Demand
        for node_id, new_demand in demand_row.items():
            node_name = str(node_id)
            if node_name in wn_sim.junction_name_list:
                node = wn_sim.get_node(node_name)
                if len(node.demand_timeseries_list) > 0:
                    node.demand_timeseries_list[0].base_value = new_demand
                    
        # Gán Demand nút rò rỉ về 0
        leak_node = wn_sim.get_node(leak_node_id)
        if len(leak_node.demand_timeseries_list) > 0:
            leak_node.demand_timeseries_list[0].base_value = 0
                    
        # Kích hoạt rò rỉ
        leak_node.add_leak(wn_sim, discharge_coeff=discharge_coeff, area=area, start_time=0)
        
        # Chạy mô phỏng
        sim = wntr.sim.EpanetSimulator(wn_sim)
        try:
            results = sim.run_sim()
            
            # Lấy nguyên cái bảng áp suất 24h (Index là thời gian, Columns là các Nút)
            pressure_all_times = results.node['pressure']
            
            # ==========================================
            # 4. LẶP QUA TỪNG GIỜ ĐỂ LƯU DATA TIME SERIES
            # ==========================================
            for t_step in time_steps:
                # Nếu thời gian này có tồn tại trong kết quả
                if t_step in pressure_all_times.index:
                    pressure_row = pressure_all_times.loc[t_step]
                    
                    # Dòng dữ liệu giờ có thêm cột Time_Hour
                    data_record = {
                        'Scenario_ID': row_index,
                        'Leak_Node': leak_node_id, 
                        'Leak_Area': area,
                        'Time_Hour': t_step / 3600  # Đổi ra giờ cho dễ đọc (0, 1, 2... 24)
                    }
                    
                    # Đổ áp suất của toàn bộ cảm biến vào
                    for node_name, p_val in pressure_row.items():
                        data_record[node_name] = p_val
                        
                    dataset_rows.append(data_record)
        except:
            continue # Bỏ qua nếu lỗi thủy lực

# ==========================================
# 5. XUẤT FILE DATASET
# ==========================================
df_final = pd.DataFrame(dataset_rows)
df_final.to_csv(output_dataset, index=False)
print(f"\n-> Xong! Dataset TimeSeries đã sẵn sàng tại: {output_dataset}")
print(f"Kích thước ma trận khủng: {df_final.shape[0]} dòng x {df_final.shape[1]} cột.")

