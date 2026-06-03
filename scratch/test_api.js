const http = require('http');

// Get expiries first from metadata endpoint
const metadataUrl = 'http://localhost:8081/api/options/metadata?index=NIFTY&exchange=NSE';

http.get(metadataUrl, (res) => {
  let data = '';
  res.on('data', (chunk) => { data += chunk; });
  res.on('end', () => {
    console.log("Metadata status:", res.statusCode);
    try {
      const meta = JSON.parse(data);
      console.log("Spot price:", meta.spot_price);
      console.log("ATM strike:", meta.atm_strike);
      console.log("Expiries:", meta.expiries);
      
      if (meta.expiries && meta.expiries.length > 0) {
        const activeExpiry = meta.expiries[0];
        const chainUrl = `http://localhost:8081/api/options/chain?expiry=${activeExpiry}&index=NIFTY&exchange=NSE`;
        console.log("\nFetching option chain for expiry:", activeExpiry, "URL:", chainUrl);
        
        http.get(chainUrl, (cRes) => {
          let cData = '';
          cRes.on('data', (chunk) => { cData += chunk; });
          cRes.on('end', () => {
            console.log("Chain response status:", cRes.statusCode);
            try {
              const chainJson = JSON.parse(cData);
              if (chainJson.strikes && chainJson.strikes.length > 0) {
                console.log("\nFirst strike row:\n", JSON.stringify(chainJson.strikes[0], null, 2));
              } else {
                console.log("Chain strikes empty:", chainJson);
              }
            } catch (e) {
              console.log("Failed to parse chain response. Body prefix:", cData.substring(0, 1000));
            }
          });
        });
      }
    } catch (e) {
      console.log("Failed to parse metadata. Body:", data);
    }
  });
});
