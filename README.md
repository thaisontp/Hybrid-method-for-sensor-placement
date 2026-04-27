1. Using Shannon Entropy to quantify and prioritize locations with the highest signal
sensitivity to leakage incidents
2. Evaluating the statistical correlation between measurement points to eliminate dupli-
cate data streams, ensuring the independence of each sensor
3. Establishing a minimum physical distance constraint to prevent local concentration
of monitoring devices.


**Run test 1 to create dataset
  in test 1, replace the data file .inp folloew the senario leak pipe 113,163,191,249,249,295 in the code to generate the dataset for each leak
  also replace the name output file csv for each test .inp

inp_file = 'Net3.inp'
save_file = 'demand_scenarios.csv'
csv_file = 'demand_scenarios.csv'
inp_file = '113.inp'          
demand_csv = 'demand_scenarios.csv'
output_dataset = '113_TimeSeries_LeakArea_Dataset.csv'

**Run test 2 to have the final
  do the same replace data .csv for each leak test
  
csv_file = '113_TimeSeries_LeakArea_Dataset.csv' 

**Run test 3 for heeatmap
