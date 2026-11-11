import { useEffect, useState } from "react";
import API from "../services/api";
import CoinChart from "../components/CoinChart";

const Dashboard = () => {

  const [coins, setCoins] = useState([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [watchlist, setWatchlist] = useState(() => {

  const saved = localStorage.getItem("watchlist");

  return saved ? JSON.parse(saved) : [];

});

  useEffect(() => {

  fetchCoins();

  const interval = setInterval(() => {
    fetchCoins();
  }, 10000);

  return () => clearInterval(interval);

}, []);

   useEffect(() => {

  localStorage.setItem(
    "watchlist",
    JSON.stringify(watchlist)
  );

}, [watchlist]);

const fetchCoins = async () => {

    try {

      const response = await API.get("/market");

      const marketData = response.data;

      const updatedCoins = await Promise.all(

        marketData.map(async (coin) => {

          const symbol = coin.symbol.toUpperCase();

          // Skip stablecoins for signals
          if (symbol === "USDT" || symbol === "USDC") {

            return {
              ...coin,
              signal: null,
            };
          }

          try {
           // setLoading(true);
            const signalResponse = await API.get(
              `/signal/${symbol}USDT`
            );

            return {
              ...coin,
              signal: signalResponse.data,
            };

          } catch (error) {

            return {
              ...coin,
              signal: null,
            };
          }
        })
      );

      setCoins(updatedCoins);
      //setLoading(true);
      setInitialLoading(false);

    } 
    catch (error) {

      console.log(error);
      setInitialLoading(false);
    }
  };
const filteredCoins = coins
  .filter((coin) =>
    coin.name.toLowerCase().includes(search.toLowerCase()) ||
    coin.symbol.toLowerCase().includes(search.toLowerCase())
  )
  .sort((a, b) => {

    const aWatchlisted = watchlist.includes(a.id);
    const bWatchlisted = watchlist.includes(b.id);

    if (aWatchlisted && !bWatchlisted) return -1;

    if (!aWatchlisted && bWatchlisted) return 1;

    return 0;
  });
const topGainers = [...coins]
  .sort(
    (a, b) =>
      b.price_change_percentage_24h -
      a.price_change_percentage_24h
  )
  .slice(0, 3);

const topLosers = [...coins]
  .sort(
    (a, b) =>
      a.price_change_percentage_24h -
      b.price_change_percentage_24h
  )
  .slice(0, 3);
const toggleWatchlist = (coinId) => {

  if (watchlist.includes(coinId)) {

    setWatchlist(
      watchlist.filter((id) => id !== coinId)
    );

  } else {

    setWatchlist([...watchlist, coinId]);
  }
};

 const getSignalStyles = (signal) => {

  if (signal === "BUY") {

    return {
      text: "text-green-400",
      bg: "bg-green-500/20 border border-green-500"
    };
  }

  if (signal === "SELL") {

    return {
      text: "text-red-400",
      bg: "bg-red-500/20 border border-red-500"
    };
  }

  if (signal === "UNAVAILABLE") {

    return {
      text: "text-gray-400",
      bg: "bg-gray-500/20 border border-gray-500"
    };
  }

  return {
    text: "text-yellow-400",
    bg: "bg-yellow-500/20 border border-yellow-500"
  };
};

  return (

            <div className="
            px-4
            py-6
            md:px-8
            bg-gradient-to-br from-black via-zinc-950 to-black
            min-h-screen
            text-white
          ">

        <h1 className="
            text-3xl
            md:text-5xl
            font-bold
            mb-8
            text-center
          ">
        Crypto AI Dashboard
      </h1>

      <div className="mb-8 flex justify-center">

      <input
        type="text"
        placeholder="Search coin..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="
          bg-zinc-900
          border
          border-zinc-700
          rounded-xl
          px-4
          py-3
          w-full
          max-w-md
          text-white
          outline-none
          focus:border-yellow-500
        "
      />

    </div>
<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">

  {/* Top Gainers */}
  <div className="bg-zinc-900 p-5 rounded-2xl border border-zinc-800">

    <h2 className="text-2xl font-bold text-green-400 mb-4">
      🚀 Top Gainers
    </h2>

    <div className="space-y-3">

      {topGainers.map((coin) => (

        <div
          key={coin.id}
          className="flex justify-between items-center"
        >

          <div className="flex items-center gap-3">

            <img
              src={coin.image}
              alt={coin.name}
              className="w-8 h-8"
            />

            <div>

              <p className="font-semibold">
                {coin.symbol.toUpperCase()}
              </p>

              <p className="text-sm text-zinc-400">
                ${coin.current_price}
              </p>

            </div>

          </div>

          <p className="text-green-400 font-bold">

            {coin.price_change_percentage_24h?.toFixed(2)}%

          </p>

        </div>

      ))}

    </div>

  </div>

  {/* Top Losers */}
  <div className="bg-zinc-900 p-5 rounded-2xl border border-zinc-800">

    <h2 className="text-2xl font-bold text-red-400 mb-4">
      📉 Top Losers
    </h2>

    <div className="space-y-3">

      {topLosers.map((coin) => (

        <div
          key={coin.id}
          className="flex justify-between items-center"
        >

          <div className="flex items-center gap-3">

            <img
              src={coin.image}
              alt={coin.name}
              className="w-8 h-8"
            />

            <div>

              <p className="font-semibold">
                {coin.symbol.toUpperCase()}
              </p>

              <p className="text-sm text-zinc-400">
                ${coin.current_price}
              </p>

            </div>

          </div>

          <p className="text-red-400 font-bold">

            {coin.price_change_percentage_24h?.toFixed(2)}%

          </p>

        </div>

      ))}

    </div>

  </div>

</div>
      {initialLoading ? (

  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">

    {[...Array(6)].map((_, index) => (

      <div
        key={index}
        className="
          bg-zinc-900
          p-5
          rounded-2xl
          border
          border-zinc-800
          animate-pulse
        "
      >

        <div className="h-6 bg-zinc-700 rounded w-1/2 mb-4"></div>

        <div className="h-8 bg-zinc-700 rounded w-2/3 mb-4"></div>

        <div className="h-20 bg-zinc-700 rounded mb-4"></div>

        <div className="h-6 bg-zinc-700 rounded w-1/3"></div>

      </div>

    ))}

  </div>

) : (

  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">

    {filteredCoins.map((coin) => (

      <div
        key={coin.id}
        className=" bg-zinc-900 p-4 md:p-5 rounded-2xl  border border-zinc-800" >

        {/* Coin Header */}
        <div className="flex justify-end">

          <button
            onClick={() => toggleWatchlist(coin.id)}
            className="text-2xl"
          >
            {watchlist.includes(coin.id)
              ? "⭐"
              : "☆"}
          </button>

        </div>

        <div className="flex items-center gap-3">

          <img
            src={coin.image}
            alt={coin.name}
            className="w-10 h-10"
          />

          <div>

            <h2 className="text-xl font-semibold">
              {coin.name}
            </h2>

            <p className="text-zinc-400 uppercase">
              {coin.symbol}
            </p>

          </div>

        </div>

        {/* Price */}
        <div className="mt-5">

          <p className="text-2xl md:text-3xl font-bold">
            ${coin.current_price}
          </p>

          <p
            className={`mt-2 ${
              coin.price_change_percentage_24h > 0
                ? "text-green-500"
                : "text-red-500"
            }`}
          >
            {coin.price_change_percentage_24h?.toFixed(2)}%
          </p>

        </div>

        {/* Chart */}
        {coin.sparkline_in_7d?.price && (

          <CoinChart
            prices={coin.sparkline_in_7d.price}
          />

        )}

        {/* Signal Section */}
        {coin.signal && (

          <div className="mt-5 border-t border-zinc-700 pt-4">

            <div
              className={`
                inline-flex
                px-4
                py-2
                rounded-xl
                text-lg
                font-bold
                ${getSignalStyles(coin.signal.signal).text}
                ${getSignalStyles(coin.signal.signal).bg}
              `}
            >
              {coin.signal.signal}
            </div>

            <p className="text-sm text-zinc-400 mt-2">
              Confidence: {coin.signal.confidence}%
            </p>

            <p className="text-sm text-zinc-400">
              RSI: {coin.signal.rsi}
            </p>

            <p className="text-sm text-zinc-400">
              MACD: {coin.signal.macd}
            </p>

            <p className="text-sm text-zinc-400">
              Price: {coin.signal.price}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">

              {coin.signal.reasons.map((reason, index) => (

                <span
                  key={index}
                  className="bg-zinc-800 text-xs px-2 py-1 rounded-lg"
                >
                  {reason}
                </span>

              ))}

            </div>

          </div>

        )}

      </div>

    ))}

  </div>

)}

    </div>
  );
};

export default Dashboard;