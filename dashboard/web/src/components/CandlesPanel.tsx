import { useEffect, useRef } from "react";
import { ColorType, LineStyle, createChart } from "lightweight-charts";
import type { AnalysisResponse, ChartResponse } from "../lib/api";

type Props = {
  data: ChartResponse | null;
  analysis: AnalysisResponse | null;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function buildIndicators(data: ChartResponse) {
  const closes = data.candles.map((item) => item.close);
  const highs = data.candles.map((item) => item.high);
  const lows = data.candles.map((item) => item.low);

  const sma = (values: number[], length: number, index: number): number | null => {
    if (index + 1 < length) {
      return null;
    }
    const window = values.slice(index - length + 1, index + 1);
    return window.reduce((sum, value) => sum + value, 0) / length;
  };

  const ema = (values: number[], span: number): Array<number | null> => {
    const multiplier = 2 / (span + 1);
    const result: Array<number | null> = [];
    let previous: number | null = null;
    values.forEach((value, index) => {
      if (index === 0) {
        previous = value;
      } else if (previous !== null) {
        previous = value * multiplier + previous * (1 - multiplier);
      }
      result.push(previous);
    });
    return result;
  };

  const ma20 = closes.map((_, index) => sma(closes, 20, index));
  const std20 = closes.map((_, index) => {
    if (index + 1 < 20) {
      return null;
    }
    const window = closes.slice(index - 19, index + 1);
    const mean = ma20[index] ?? 0;
    const variance = window.reduce((sum, value) => sum + (value - mean) ** 2, 0) / window.length;
    return Math.sqrt(variance);
  });

  const bollinger = closes.map((close, index) => {
    const mid = ma20[index];
    const std = std20[index];
    return {
      time: data.candles[index].time,
      upper: mid !== null && std !== null ? mid + std * 2 : null,
      mid,
      lower: mid !== null && std !== null ? mid - std * 2 : null,
      close
    };
  });

  const kFast = closes.map((close, index) => {
    if (index + 1 < 9) {
      return null;
    }
    const low9 = Math.min(...lows.slice(index - 8, index + 1));
    const high9 = Math.max(...highs.slice(index - 8, index + 1));
    if (high9 === low9) {
      return 50;
    }
    return ((close - low9) / (high9 - low9)) * 100;
  });

  const smooth = (values: Array<number | null>, length: number): Array<number | null> => {
    return values.map((_, index) => {
      const window = values.slice(Math.max(0, index - length + 1), index + 1).filter((value): value is number => value !== null);
      if (window.length < length) {
        return null;
      }
      return window.reduce((sum, value) => sum + value, 0) / window.length;
    });
  };

  const kdK = smooth(kFast, 3);
  const kdD = smooth(kdK, 3);

  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const macdDif = closes.map((_, index) => {
    const fast = ema12[index];
    const slow = ema26[index];
    return fast !== null && slow !== null ? fast - slow : null;
  });
  const macdSignal = ema(macdDif.map((value) => value ?? 0), 9).map((value, index) => (macdDif[index] === null ? null : value));
  const macdHist = macdDif.map((value, index) => {
    const signal = macdSignal[index];
    return value !== null && signal !== null ? value - signal : null;
  });

  return { bollinger, kdK, kdD, macdDif, macdSignal, macdHist };
}

function toLineData(values: Array<{ time: string; value: number | null }>) {
  return values.flatMap((item) => (item.value === null || Number.isNaN(item.value) ? [] : [{ time: item.time, value: item.value }]));
}

export function CandlesPanel({ data, analysis }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data?.candles.length) {
      return;
    }

    const container = containerRef.current;
    const indicators = buildIndicators(data);
    const chart = createChart(container, {
      autoSize: true,
      height: 680,
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
      scaleMargins: { top: 0.05, bottom: 0.52 }
    });

    const bbUpperSeries = chart.addLineSeries({
      color: "#ff8a65",
      lineWidth: 1,
      priceScaleId: "right",
      lastValueVisible: false,
      priceLineVisible: false
    });
    bbUpperSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.52 } });

    const bbMidSeries = chart.addLineSeries({
      color: "#4fc3f7",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceScaleId: "right",
      lastValueVisible: false,
      priceLineVisible: false
    });
    bbMidSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.52 } });

    const bbLowerSeries = chart.addLineSeries({
      color: "#66bb6a",
      lineWidth: 1,
      priceScaleId: "right",
      lastValueVisible: false,
      priceLineVisible: false
    });
    bbLowerSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.52 } });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      color: "#4e566b"
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.58, bottom: 0.28 }
    });

    const kdKSeries = chart.addLineSeries({
      color: "#ffd166",
      lineWidth: 2,
      priceScaleId: "kd",
      lastValueVisible: false,
      priceLineVisible: false
    });
    kdKSeries.priceScale().applyOptions({
      autoScale: false,
      scaleMargins: { top: 0.76, bottom: 0.14 }
    });
    const kdDSeries = chart.addLineSeries({
      color: "#ff5c8a",
      lineWidth: 2,
      priceScaleId: "kd",
      lastValueVisible: false,
      priceLineVisible: false
    });
    kdDSeries.priceScale().applyOptions({
      autoScale: false,
      scaleMargins: { top: 0.76, bottom: 0.14 }
    });
    kdKSeries.createPriceLine({ price: 80, color: "#5f687a", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "80" });
    kdKSeries.createPriceLine({ price: 20, color: "#5f687a", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "20" });

    const macdHistSeries = chart.addHistogramSeries({
      priceScaleId: "macd",
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      lastValueVisible: false,
      priceLineVisible: false
    });
    macdHistSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.88, bottom: 0.02 }
    });
    const macdDifSeries = chart.addLineSeries({
      color: "#ffb703",
      lineWidth: 2,
      priceScaleId: "macd",
      lastValueVisible: false,
      priceLineVisible: false
    });
    macdDifSeries.priceScale().applyOptions({ scaleMargins: { top: 0.88, bottom: 0.02 } });
    const macdSignalSeries = chart.addLineSeries({
      color: "#8ecae6",
      lineWidth: 2,
      priceScaleId: "macd",
      lastValueVisible: false,
      priceLineVisible: false
    });
    macdSignalSeries.priceScale().applyOptions({ scaleMargins: { top: 0.88, bottom: 0.02 } });
    macdDifSeries.createPriceLine({ price: 0, color: "#5f687a", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "0" });

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

    bbUpperSeries.setData(toLineData(indicators.bollinger.map((item) => ({ time: item.time, value: item.upper }))));
    bbMidSeries.setData(toLineData(indicators.bollinger.map((item) => ({ time: item.time, value: item.mid }))));
    bbLowerSeries.setData(toLineData(indicators.bollinger.map((item) => ({ time: item.time, value: item.lower }))));

    kdKSeries.setData(toLineData(data.candles.map((item, index) => ({ time: item.time, value: indicators.kdK[index] === null ? null : clamp(indicators.kdK[index] as number, 0, 100) }))));
    kdDSeries.setData(toLineData(data.candles.map((item, index) => ({ time: item.time, value: indicators.kdD[index] === null ? null : clamp(indicators.kdD[index] as number, 0, 100) }))));

    macdDifSeries.setData(toLineData(data.candles.map((item, index) => ({ time: item.time, value: indicators.macdDif[index] }))));
    macdSignalSeries.setData(toLineData(data.candles.map((item, index) => ({ time: item.time, value: indicators.macdSignal[index] }))));
    macdHistSeries.setData(
      data.candles.flatMap((item, index) => {
        const value = indicators.macdHist[index];
        if (value === null || Number.isNaN(value)) {
          return [];
        }
        return [{
          time: item.time,
          value,
          color: value >= 0 ? "#ef5350aa" : "#26a69aaa"
        }];
      })
    );

    if (analysis?.key_levels) {
      const levelGroups = [
        { title: "壓力", zone: analysis.key_levels.resistance, color: "#ff6b6b" },
        { title: "回檔", zone: analysis.key_levels.pullback, color: "#ffd166" },
        { title: "支撐", zone: analysis.key_levels.support, color: "#4dd4ac" }
      ];
      levelGroups.forEach((group) => {
        candleSeries.createPriceLine({
          price: group.zone.low,
          color: group.color,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: group.title + "下緣"
        });
        candleSeries.createPriceLine({
          price: group.zone.high,
          color: group.color,
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: group.title + "上緣"
        });
      });
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [analysis, data]);

  return (
    <section className="panel chart-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">主圖</p>
          <h2>日線主圖 / 量能 / KD / MACD</h2>
        </div>
        <div className="panel-meta">
          <span>{data?.timeframe ?? "daily"}</span>
          <span>{String(data?.meta.returned_rows ?? 0) + " bars"}</span>
          <span>含布林與關鍵價位</span>
        </div>
      </div>
      <div ref={containerRef} className="chart-canvas" />
    </section>
  );
}
