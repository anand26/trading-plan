"""
Smart Parameter Generation using Latin Hypercube Sampling
=========================================================
Generates optimized parameter combinations for TQQQ/SQQQ strategy.

Uses Latin Hypercube Sampling (LHS) to efficiently cover parameter space
with far fewer combinations than full grid search.

Instead of 244M combinations, we generate 1000 representative samples.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import qmc  # For Latin Hypercube Sampling

def generate_lhs_parameters(n_samples: int = 1000, random_state: int = 42) -> pd.DataFrame:
    """
    Generate parameter combinations using Latin Hypercube Sampling.
    
    Parameters:
    - n_samples: Number of parameter combinations to generate
    - random_state: Random seed for reproducibility
    
    Returns:
    - DataFrame with parameter combinations
    """
    
    # Define parameter ranges (min, max) for TQQQ/SQQQ strategy
    param_ranges = {
        # RSI Parameters
        'rsi_period': (10, 21),           # RSI window: 10-21 periods
        'rsi_oversold': (20, 35),         # Oversold threshold: 20-35
        'rsi_overbought': (65, 80),       # Overbought threshold: 65-80
        
        # Bollinger Bands
        'bb_period': (15, 30),            # BB window: 15-30 periods
        'bb_std_dev': (1.5, 2.5),        # Standard deviations: 1.5-2.5
        
        # EMA Trend Filter
        'ema_fast_period': (5, 15),       # Fast EMA: 5-15 periods
        'ema_slow_period': (15, 30),      # Slow EMA: 15-30 periods
        
        # Risk Management
        'stop_loss_pct': (0.01, 0.03),    # Stop loss: 1-3%
        'take_profit_pct': (0.02, 0.05),  # Take profit: 2-5%
        
        # Position Sizing (Pyramiding)
        'position_size_level1': (0.3, 0.6),   # Level 1: 30-60%
        'position_size_level2': (0.2, 0.4),   # Level 2: 20-40%
        'position_size_level3': (0.1, 0.3),   # Level 3: 10-30%
    }
    
    # Set up Latin Hypercube Sampler
    n_params = len(param_ranges)
    sampler = qmc.LatinHypercube(d=n_params, seed=random_state)
    
    # Generate samples in [0, 1] space
    samples = sampler.random(n=n_samples)
    
    # Scale samples to parameter ranges
    param_names = list(param_ranges.keys())
    scaled_samples = {}
    
    for i, param_name in enumerate(param_names):
        min_val, max_val = param_ranges[param_name]
        
        if param_name in ['rsi_period', 'bb_period', 'ema_fast_period', 'ema_slow_period']:
            # Integer parameters
            scaled_samples[param_name] = np.round(
                samples[:, i] * (max_val - min_val) + min_val
            ).astype(int)
        else:
            # Float parameters
            scaled_samples[param_name] = samples[:, i] * (max_val - min_val) + min_val
    
    # Create DataFrame
    df = pd.DataFrame(scaled_samples)
    
    # Apply business logic constraints
    df = apply_parameter_constraints(df)
    
    # Round float values to reasonable precision
    float_columns = ['rsi_oversold', 'rsi_overbought', 'bb_std_dev', 
                     'stop_loss_pct', 'take_profit_pct',
                     'position_size_level1', 'position_size_level2', 'position_size_level3']
    
    for col in float_columns:
        if col in ['stop_loss_pct', 'take_profit_pct']:
            df[col] = np.round(df[col], 3)  # 3 decimal places for percentages
        elif col in ['position_size_level1', 'position_size_level2', 'position_size_level3']:
            df[col] = np.round(df[col], 2)  # 2 decimal places for position sizes
        else:
            df[col] = np.round(df[col], 1)  # 1 decimal place for RSI/BB values
    
    return df

def apply_parameter_constraints(df: pd.DataFrame) -> pd.DataFrame:
    """Apply business logic constraints to parameters."""
    
    # Constraint 1: RSI oversold < RSI overbought (with minimum gap)
    min_gap = 25  # Minimum gap between oversold and overbought
    mask = (df['rsi_overbought'] - df['rsi_oversold']) < min_gap
    df.loc[mask, 'rsi_overbought'] = df.loc[mask, 'rsi_oversold'] + min_gap
    df['rsi_overbought'] = np.clip(df['rsi_overbought'], 65, 80)  # Keep within bounds
    
    # Constraint 2: EMA fast < EMA slow
    mask = df['ema_fast_period'] >= df['ema_slow_period']
    df.loc[mask, 'ema_slow_period'] = df.loc[mask, 'ema_fast_period'] + np.random.randint(5, 15, size=mask.sum())
    df['ema_slow_period'] = np.clip(df['ema_slow_period'], 15, 30)
    
    # Constraint 3: Position sizes should sum to approximately 1.0 (allow some flexibility)
    total_position = df['position_size_level1'] + df['position_size_level2'] + df['position_size_level3']
    
    # Normalize to sum close to 1.0 (allow 0.9-1.1 range)
    target_sum = np.random.uniform(0.95, 1.05, size=len(df))
    scale_factor = target_sum / total_position
    
    df['position_size_level1'] *= scale_factor
    df['position_size_level2'] *= scale_factor
    df['position_size_level3'] *= scale_factor
    
    # Constraint 4: Stop loss < Take profit
    mask = df['stop_loss_pct'] >= df['take_profit_pct']
    df.loc[mask, 'take_profit_pct'] = df.loc[mask, 'stop_loss_pct'] + 0.01  # Add 1% buffer
    df['take_profit_pct'] = np.clip(df['take_profit_pct'], 0.02, 0.05)
    
    return df

def add_regime_specific_sets(df: pd.DataFrame) -> pd.DataFrame:
    """Add some regime-specific parameter sets based on market conditions."""
    
    # High volatility set (tighter stops, wider RSI bands)
    high_vol_params = {
        'rsi_period': [10, 12],
        'rsi_oversold': [25, 30],
        'rsi_overbought': [70, 75],
        'bb_period': [15, 20],
        'bb_std_dev': [2.0, 2.2],
        'ema_fast_period': [8, 10],
        'ema_slow_period': [21, 25],
        'stop_loss_pct': [0.015, 0.02],
        'take_profit_pct': [0.025, 0.03],
        'position_size_level1': [0.4, 0.5],
        'position_size_level2': [0.3, 0.35],
        'position_size_level3': [0.2, 0.25],
    }
    
    # Trending market set (looser stops, momentum-focused)
    trend_params = {
        'rsi_period': [14, 18],
        'rsi_oversold': [20, 25],
        'rsi_overbought': [75, 80],
        'bb_period': [20, 25],
        'bb_std_dev': [1.8, 2.2],
        'ema_fast_period': [9, 12],
        'ema_slow_period': [21, 28],
        'stop_loss_pct': [0.02, 0.025],
        'take_profit_pct': [0.03, 0.04],
        'position_size_level1': [0.5, 0.6],
        'position_size_level2': [0.25, 0.3],
        'position_size_level3': [0.15, 0.2],
    }
    
    # Generate small sets for each regime (50 combinations each)
    regime_dfs = []
    
    for params in [high_vol_params, trend_params]:
        # Create mini-LHS for each regime
        mini_sampler = qmc.LatinHypercube(d=len(params), seed=np.random.randint(1000))
        mini_samples = mini_sampler.random(n=25)  # 25 samples per regime
        
        regime_df = pd.DataFrame()
        for i, (param, (min_val, max_val)) in enumerate(params.items()):
            if param in ['rsi_period', 'bb_period', 'ema_fast_period', 'ema_slow_period']:
                regime_df[param] = np.round(
                    mini_samples[:, i] * (max_val - min_val) + min_val
                ).astype(int)
            else:
                values = mini_samples[:, i] * (max_val - min_val) + min_val
                if param in ['stop_loss_pct', 'take_profit_pct']:
                    regime_df[param] = np.round(values, 3)
                else:
                    regime_df[param] = np.round(values, 2)
        
        regime_dfs.append(regime_df)
    
    # Combine all dataframes
    final_df = pd.concat([df] + regime_dfs, ignore_index=True)
    
    # Remove any duplicates and shuffle
    final_df = final_df.drop_duplicates().sample(frac=1, random_state=42).reset_index(drop=True)
    
    return final_df

def main():
    """Generate smart parameter combinations and save to CSV."""
    
    print("🧠 Generating Smart Parameter Combinations using Latin Hypercube Sampling")
    print("=" * 70)
    
    # Generate base LHS samples
    print("📊 Generating 900 LHS base samples...")
    df_base = generate_lhs_parameters(n_samples=900, random_state=42)
    
    # Add regime-specific sets
    print("🎯 Adding 50 regime-specific combinations...")
    df_final = add_regime_specific_sets(df_base)
    
    print(f"✅ Generated {len(df_final)} unique parameter combinations")
    
    # Save to CSV
    output_path = Path(__file__).parent / "parameter_combinations.csv"
    df_final.to_csv(output_path, index=False)
    
    print(f"💾 Saved to: {output_path}")
    
    # Display statistics
    print("\n📈 Parameter Range Summary:")
    print("-" * 50)
    
    for col in df_final.columns:
        min_val = df_final[col].min()
        max_val = df_final[col].max()
        mean_val = df_final[col].mean()
        
        if col in ['rsi_period', 'bb_period', 'ema_fast_period', 'ema_slow_period']:
            print(f"{col:20}: {min_val:3.0f} - {max_val:3.0f} (avg: {mean_val:4.1f})")
        else:
            print(f"{col:20}: {min_val:5.3f} - {max_val:5.3f} (avg: {mean_val:5.3f})")
    
    # Display coverage efficiency
    print(f"\n🚀 Space-Filling Efficiency:")
    print(f"   • Instead of millions of grid combinations")
    print(f"   • Using {len(df_final)} strategically sampled points")
    print(f"   • ~99.9% reduction with better parameter space coverage")
    
    print(f"\n⏱️  Estimated Runtime: {len(df_final) * 9 / 60:.1f} minutes")
    print("🎯 Ready for optimization!")

if __name__ == "__main__":
    main()