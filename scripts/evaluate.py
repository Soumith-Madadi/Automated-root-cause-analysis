#!/usr/bin/env python3
"""Evaluation harness that runs replay on multiple incidents and computes aggregate metrics."""
import asyncio
import os
import sys
import json
from typing import List, Dict, Any

import asyncpg
from clickhouse_driver import Client

# Import replay function
from replay_incident import replay_incident


async def evaluate_all_incidents() -> Dict[str, Any]:
    """Evaluate all labeled incidents."""
    # Connect to services
    clickhouse_client = Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        database=os.getenv("CLICKHOUSE_DB", "rca")
    )
    
    postgres_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "rca"),
        user=os.getenv("POSTGRES_USER", "rca"),
        password=os.getenv("POSTGRES_PASSWORD", "rca_password")
    )
    
    try:
        # Get all incidents with labels
        async with postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT i.id
                FROM incidents i
                JOIN labels l ON i.id = l.incident_id
                """
            )
        
        incident_ids = [str(row['id']) for row in rows]
        
        if not incident_ids:
            print("No labeled incidents found")
            return {
                'num_incidents': 0,
                'precision_at_1': None,
                'precision_at_3': None,
                'mrr': None,
                'avg_time_to_detect': None
            }
        
        print(f"Evaluating {len(incident_ids)} incidents...")
        
        results_list = []
        for incident_id in incident_ids:
            try:
                result = await replay_incident(incident_id, clickhouse_client, postgres_pool)
                results_list.append(result)
            except Exception as e:
                print(f"Error evaluating incident {incident_id}: {e}")
        
        # Aggregate metrics
        precision_at_1_values = [r['precision_at_1'] for r in results_list if r['precision_at_1'] is not None]
        precision_at_3_values = [r['precision_at_3'] for r in results_list if r['precision_at_3'] is not None]
        mrr_values = [r['mrr'] for r in results_list if r['mrr'] is not None]
        time_to_detect_values = [r['time_to_detect_minutes'] for r in results_list if r['time_to_detect_minutes'] is not None]
        
        aggregate = {
            'num_incidents': len(results_list),
            'precision_at_1': sum(precision_at_1_values) / len(precision_at_1_values) if precision_at_1_values else None,
            'precision_at_3': sum(precision_at_3_values) / len(precision_at_3_values) if precision_at_3_values else None,
            'mrr': sum(mrr_values) / len(mrr_values) if mrr_values else None,
            'avg_time_to_detect_minutes': sum(time_to_detect_values) / len(time_to_detect_values) if time_to_detect_values else None,
            'individual_results': results_list
        }
        
        return aggregate
    
    finally:
        await postgres_pool.close()
        clickhouse_client.disconnect()


async def main():
    """Main entry point."""
    print("=" * 60)
    print("RCA System Evaluation")
    print("=" * 60)
    
    results = await evaluate_all_incidents()
    
    print("\n" + "=" * 60)
    print("Aggregate Metrics")
    print("=" * 60)
    print(f"Number of incidents evaluated: {results['num_incidents']}")
    print(f"Precision@1: {results['precision_at_1']:.3f}" if results['precision_at_1'] is not None else "Precision@1: N/A")
    print(f"Precision@3: {results['precision_at_3']:.3f}" if results['precision_at_3'] is not None else "Precision@3: N/A")
    print(f"MRR: {results['mrr']:.3f}" if results['mrr'] is not None else "MRR: N/A")
    print(f"Avg Time to Detect: {results['avg_time_to_detect_minutes']:.2f} minutes" if results['avg_time_to_detect_minutes'] is not None else "Avg Time to Detect: N/A")
    
    # Save results to file
    output_file = 'evaluation_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())


