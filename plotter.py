from dash import Dash, dcc, html
from dash.dependencies import Output, Input
import plotly.express as px
from logger import *
from CT_calibration import * 

# ------------------- Dash App -------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H2("ESP32 Live Sensor Data"),
    dcc.Graph(id="live-graph"),
    html.Div(id="on-off-time", style={"marginTop": 20, "fontSize": 18}),
    dcc.Interval(
        id="interval-component",
        interval=30*1000,  # update every 10 seconds
        n_intervals=0
    )
])

@app.callback(
    [Output("live-graph", "figure"),
     Output("on-off-time", "children")],
    [Input("interval-component", "n_intervals")]
)


def update_graph(n):
    df = get_data()

    last_time = df["timestamp"].max()
    start_time = last_time - pd.Timedelta(hours=24)
    # df = df[df["timestamp"] >= start_time].reset_index(drop=True)
    # Calculate time differences
    df["time_diff"] = df["timestamp"].diff().dt.total_seconds().fillna(0)

    # If gap > 5 minutes, treat it as 0 (power/WiFi outage)
    df.loc[df["time_diff"] > 300, "time_diff"] = 0

    # Determine Fridge ON/OFF
    df["Fridge_ON"] = df["value"] > 80

    # Compute ON/OFF durations
    total_on_hours = df.loc[df["Fridge_ON"], "time_diff"].sum() / 3600
    total_off_hours = df.loc[~df["Fridge_ON"], "time_diff"].sum() / 3600

    # Compute total available logged data
    total_data_hours = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).total_seconds() / 3600

        # --- NEW: Compute energy consumption ---
    # Current as average of current and previous value
    df["current"] = df["value"].rolling(2).mean()
    
    # Apply calibration to get actual current in Amps
    df["current_actual"] = df["current"].apply(get_current)
    
    # Instantaneous power in W
    df["power_W"] = df["current_actual"] * 210  # 210V approximation
    
    # Energy for each interval in Wh
    df["energy_Wh"] = df["power_W"] * (df["time_diff"] / 3600)
    
    # Only consider energy when fridge is ON
    df["energy_Wh_ON"] = df["energy_Wh"].where(df["Fridge_ON"], 0)
    
    # Total energy in kWh
    total_kwh = df["energy_Wh_ON"].sum() / 1000
    
    # Energy in last 24 hours (today usage)
    today_kwh = df.loc[df["timestamp"] >= start_time, "energy_Wh_ON"].sum() / 1000
    
    # Daily average usage (based on available data)
    num_days = total_data_hours / 24
    daily_avg_kwh = total_kwh / num_days if num_days > 0 else 0

    # Create scatter plot
    fig = px.scatter(
        df, 
        x="timestamp", 
        y="value",
        color="Fridge_ON",
        color_discrete_map={True: "green", False: "red"},
        title="Sensor Value vs Time (Scatter View)"
    )
    fig.update_layout(
        xaxis_title="Timestamp",
        yaxis_title="Sensor Value",
        legend_title="Fridge Status",
        xaxis=dict(range=[start_time, last_time+pd.Timedelta(hours=1.5)])  # horizontal zoom on last 24 hours
    )

    # Get last update timestamp
    last_update = df["timestamp"].max().strftime("%Y-%m-%d %H:%M:%S")

    # Display ON/OFF time and last update
    # on_off_text = (
    #     f"✅Last update: {last_update}\n"
    #     f"✅Total ON: {total_on_hours:.3f} hours\n"
    #     f"✅Total OFF: {total_off_hours:.3f} hours\n"
    #     f"✅Total available data: {total_data_hours:.3f} hours"
    # )

    # Display text
    on_off_text = (
        f"✅ Last update: {last_update}\n"
        f"✅ Total ON: {total_on_hours:.3f} hours\n"
        f"✅ Total OFF: {total_off_hours:.3f} hours\n"
        f"✅ Total available data: {total_data_hours:.3f} hours\n"
        f"⚡ Total Energy Usage: {total_kwh:.3f} kWh\n"
        f"⚡ Last 24 hour Usage: {today_kwh:.3f} kWh\n"
        f"⚡ Daily Average Usage: {daily_avg_kwh:.3f} kWh"
    )

    return fig, on_off_text


if __name__ == "__main__":
    app.run(debug=True)

