import { useEffect, useRef } from "react";
import { ColorType, createChart } from "lightweight-charts";
import type { ChartResponse } from "../lib/api";

type Props = {
  data: ChartResponse | null;
};

export function CandlesPanel({ data }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data?.candles.length) {
      return;
    }

    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: true,
      height: 540,
      layout: {
        background: { type: ColorType.Solid, color: "#141820" },
        textColor: "#8d98ac"
      },
      grid: {
        vertLines: { color: "#242938" },
        horzLines: { color: "#242938" }
      },
      rightPriceScale: {
        borderColor: "#2d3447"
      },
      timeScale: {
        borderColor: "#2d3447"
      }
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#ef5350",
      downColor: "#26a69a",
      borderVisible: false,
      wickUpColor: "#ef5350",
      wickDownColor: "#26a69a",
      priceScaleId: "right"
    });
    candleSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.34 }
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: "#4e566b"
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.74, bottom: 0.04 }
    });

    candleSeries.setData(
      data.candles.map((item) => ({
        time: item.time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close
      }))
    );
    volumeSeries.setData(
      data.candles.map((item) => ({
        time: item.time,
        value: item.volume,
        color: item.close >= item.open ? "#ef535099" : "#26a69a99"
      }))
    );
    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [data]);

  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 1</p>
          <h2>日線主圖 + 成交量</h2>
        </div>
        <div className="panel-meta">
          <span>{data?.timeframe ?? "daily"}</span>
          <span>{String(data?.meta.returned_rows ?? 0) + " bars"}</span>
        </div>
      </div>
      <div ref={containerRef} className="chart-canvas" />
    </section>
  );
}
