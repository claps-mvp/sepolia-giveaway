# Sepolia Faucet Application

## Overview
This application provides a Sepolia Ethereum faucet service.

## Endpoints

- `POST /faucet/fund/`: Request funds to a specified wallet address.
- `GET /faucet/stats/`: Get statistics on transactions.

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
