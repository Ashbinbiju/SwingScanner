import json

def check_symbols():
    try:
        with open("OpenAPIScripMaster.json", 'r') as f:
            data = json.load(f)
            
        print(f"Loaded {len(data)} items.")
        
        target_symbols = ["3MINDIA", "5PAISA", "ABCAPITAL", "AJANTPHARM", "ORIENTCER", "SAIL"]
        
        found_map = {}
        
        for item in data:
            sym = item['symbol']
            # strict match check
            for t in target_symbols:
                if t in sym and item['exch_seg'] == 'NSE':
                    if t not in found_map:
                        found_map[t] = []
                    found_map[t].append(item['symbol'])
                    
        for t in target_symbols:
            print(f"Matches for {t}: {found_map.get(t, 'None')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_symbols()
