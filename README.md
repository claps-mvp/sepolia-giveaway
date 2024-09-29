# Sepolia Giveaway Application

## Overview
This application provides a Sepolia Ethereum giveaway service.

## Endpoints

- `POST /giveaway/fund/`: Request funds to a specified wallet address.
- `GET /giveaway/stats/`: Get statistics on transactions.

## Docker

To run the application:
1. Set valid values in .env (take template from .env.example)
2. Execute the following commands:
   ```bash
   docker compose build
   docker compose up
   ```

## Future Improvements
1. Make application async
2. Add ability to filter stats by wallet addresses
3. Refactor endpoints to use service pattern
