"""
Learning Insights page - Adaptive learning visualization and parameter optimization.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from dashboard.database import (
    get_learning_history,
    get_optimal_parameters,
    get_parameter_performance,
    get_current_parameters,
)


def render_learning():
    """Render the learning insights page."""
    st.title("🧠 Learning Insights")
    
    # Show current data source indicator
    data_source = st.session_state.get("data_source", "All")
    mode_badges = {
        "All": "🔵 All Data",
        "Backtest": "🟡 Backtest Results",
        "Paper": "🟢 Paper Trading",
        "Live": "🔴 Live Trading"
    }
    st.caption(f"**Data Source:** {mode_badges.get(data_source, data_source)}")
    
    # Check if backtest mode is selected
    if data_source == "Backtest":
        st.warning("⚠️ Learning insights are not available for backtests. Backtests only store summary metrics. Please switch to 'Paper' or 'Live' data source for learning analysis.")
        return
    
    # ==================== Optimal Parameters ====================
    st.subheader("Optimal Parameter Recommendations")
    
    optimal_df = get_optimal_parameters()
    
    if not optimal_df.empty:
        # Show recommendations
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**High Confidence Recommendations**")
            high_conf = optimal_df[optimal_df["ConfidenceScore"] >= 0.7].head(5)
            
            if not high_conf.empty:
                for _, row in high_conf.iterrows():
                    with st.container():
                        st.markdown(f"""
                        **{row['ParameterName']}**
                        - Current: `{row['CurrentValue']}`
                        - Suggested: `{row['OptimalValue']}`
                        - Confidence: {row['ConfidenceScore']:.1%}
                        - Expected Improvement: {row.get('ExpectedImprovement', 0):.1%}
                        """)
                        st.divider()
            else:
                st.info("No high-confidence recommendations available yet.")
        
        with col2:
            st.write("**Confidence Score Distribution**")
            fig = px.bar(
                optimal_df,
                x="ParameterName",
                y="ConfidenceScore",
                color="ConfidenceScore",
                color_continuous_scale=["red", "yellow", "green"],
                text=optimal_df["ConfidenceScore"].apply(lambda x: f"{x:.1%}" if x is not None else "N/A")
            )
            fig.update_layout(
                xaxis_title="Parameter",
                yaxis_title="Confidence Score",
                showlegend=False,
                height=350
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        
        # Full recommendations table
        st.write("**All Recommendations**")
        display_df = optimal_df.copy()
        display_df["ConfidenceScore"] = display_df["ConfidenceScore"].apply(lambda x: f"{x:.1%}")
        if "ExpectedImprovement" in display_df.columns:
            display_df["ExpectedImprovement"] = display_df["ExpectedImprovement"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
        display_df["LastUpdated"] = pd.to_datetime(display_df["LastUpdated"]).dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No parameter optimization data available yet. The system needs more trades to generate recommendations.")
    
    st.divider()
    
    # ==================== Parameter Performance ====================
    st.subheader("Parameter Performance Comparison")
    
    param_perf = get_parameter_performance()
    
    if not param_perf.empty:
        # Parameter selector
        param_names = param_perf["ParameterName"].unique().tolist()
        selected_param = st.selectbox("Select Parameter", param_names)
        
        filtered_df = param_perf[param_perf["ParameterName"] == selected_param]
        
        if not filtered_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # P&L by parameter value
                fig = px.bar(
                    filtered_df,
                    x="ParameterValue",
                    y="TotalPnL",
                    color="TotalPnL",
                    color_continuous_scale=["red", "gray", "green"],
                    text="TradeCount"
                )
                fig.update_layout(
                    title=f"Total P&L by {selected_param}",
                    xaxis_title="Parameter Value",
                    yaxis_title="Total P&L ($)",
                    showlegend=False,
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Win rate by parameter value
                fig = px.bar(
                    filtered_df,
                    x="ParameterValue",
                    y="WinRate",
                    color="WinRate",
                    color_continuous_scale=["red", "yellow", "green"],
                    text=filtered_df["WinRate"].apply(lambda x: f"{x:.1f}%" if x is not None else "N/A")
                )
                fig.add_hline(y=50, line_dash="dash", line_color="gray")
                fig.update_layout(
                    title=f"Win Rate by {selected_param}",
                    xaxis_title="Parameter Value",
                    yaxis_title="Win Rate (%)",
                    showlegend=False,
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Regime breakdown if available
            if "MarketRegime" in filtered_df.columns and filtered_df["MarketRegime"].notna().any():
                st.write(f"**{selected_param} Performance by Regime**")
                
                fig = px.scatter(
                    filtered_df,
                    x="ParameterValue",
                    y="WinRate",
                    color="MarketRegime",
                    size="TradeCount",
                    hover_data=["TotalPnL", "AvgPnL"]
                )
                fig.update_layout(
                    title=f"{selected_param} Performance Across Regimes",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No parameter performance data available yet.")
    
    st.divider()
    
    # ==================== Learning History ====================
    st.subheader("Learning History Timeline")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        days = st.selectbox(
            "Time Period",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"{x} days",
            key="learning_days"
        )
    
    learning_df = get_learning_history(days)
    
    if not learning_df.empty:
        # Learning events timeline
        fig = px.scatter(
            learning_df,
            x="Timestamp",
            y="LearningType",
            color="ConfidenceScore",
            size="ConfidenceScore",
            hover_data=["Description", "OldValue", "NewValue"],
            color_continuous_scale=["red", "yellow", "green"]
        )
        fig.update_layout(
            title="Learning Events Over Time",
            xaxis_title="Time",
            yaxis_title="Learning Type",
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Learning type breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            type_counts = learning_df["LearningType"].value_counts()
            fig = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                hole=0.4
            )
            fig.update_layout(
                title="Learning Events by Type",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Source breakdown
            if "Source" in learning_df.columns:
                source_counts = learning_df["Source"].value_counts()
                fig = px.pie(
                    values=source_counts.values,
                    names=source_counts.index,
                    hole=0.4
                )
                fig.update_layout(
                    title="Learning Events by Source",
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent learning events table
        st.write("**Recent Learning Events**")
        display_df = learning_df.head(20).copy()
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        display_df["ConfidenceScore"] = display_df["ConfidenceScore"].apply(lambda x: f"{x:.1%}" if x is not None else "N/A")
        
        st.dataframe(
            display_df[[
                "Timestamp", "LearningType", "Description", 
                "OldValue", "NewValue", "ConfidenceScore"
            ]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No learning history available yet.")
    
    st.divider()
    
    # ==================== Current Parameters ====================
    st.subheader("Current Algorithm Parameters")
    
    current_params = get_current_parameters()
    
    if not current_params.empty:
        # Group parameters by category (inferred from name)
        current_params["Category"] = current_params["ParameterName"].apply(
            lambda x: x.split("_")[0] if "_" in x else "General"
        )
        
        categories = current_params["Category"].unique()
        
        for category in categories:
            with st.expander(f"📁 {category.title()} Parameters", expanded=True):
                cat_params = current_params[current_params["Category"] == category]
                
                # Create a nice display
                cols = st.columns(3)
                for idx, (_, row) in enumerate(cat_params.iterrows()):
                    with cols[idx % 3]:
                        st.markdown(f"""
                        **{row['ParameterName']}**  
                        Value: `{row['ParameterValue']}`  
                        Type: {row.get('DataType', 'Unknown')}
                        """)
    else:
        st.info("No parameter data available.")
    
    st.divider()
    
    # ==================== Apply Recommendations ====================
    st.subheader("Apply Recommendations")
    
    if not optimal_df.empty:
        st.warning("⚠️ Applying parameter changes will affect live trading. Proceed with caution.")
        
        # Select recommendations to apply
        high_conf_params = optimal_df[optimal_df["ConfidenceScore"] >= 0.7]["ParameterName"].tolist()
        
        if high_conf_params:
            selected_to_apply = st.multiselect(
                "Select parameters to update",
                options=high_conf_params,
                help="Only high-confidence recommendations are shown"
            )
            
            if selected_to_apply:
                st.write("**Changes to Apply:**")
                for param in selected_to_apply:
                    row = optimal_df[optimal_df["ParameterName"] == param].iloc[0]
                    st.write(f"- {param}: `{row['CurrentValue']}` → `{row['OptimalValue']}`")
                
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("Apply Changes", type="primary"):
                        st.success("✅ Parameter update request sent to LEAN-Ops MCP server.")
                        st.info("Use the MCP tools to confirm the changes were applied.")
        else:
            st.info("No high-confidence recommendations available to apply.")
    else:
        st.info("Generate recommendations by running more backtests and trades.")


# Auto-execute when run directly by Streamlit multipage navigation
if "data_source" not in st.session_state:
    st.session_state.data_source = "All"

render_learning()
