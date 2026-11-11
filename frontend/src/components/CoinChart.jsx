import {
  LineChart,
  Line,
  ResponsiveContainer,
} from "recharts";

const CoinChart = ({ prices }) => {

  if (!prices || prices.length === 0) {
    return null;
  }

  const data = prices.map((price, index) => ({
    price,
    index,
  }));

  return (
    <div className="w-full h-24 mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="price"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default CoinChart;